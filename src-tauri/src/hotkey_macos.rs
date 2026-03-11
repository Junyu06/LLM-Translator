use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use core_foundation::runloop::{kCFRunLoopCommonModes, kCFRunLoopDefaultMode, CFRunLoop};
use core_graphics::event::{
    CallbackResult, CGEventFlags, CGEventTap, CGEventTapLocation, CGEventTapOptions,
    CGEventTapPlacement, CGEventType, EventField, KeyCode,
};
use tauri::{AppHandle, Emitter};

pub struct MacHotkeyListener {
    stop_flag: Arc<AtomicBool>,
    run_loop: Arc<Mutex<Option<CFRunLoop>>>,
    join_handle: Option<JoinHandle<()>>,
}

impl MacHotkeyListener {
    pub fn start(
        app: AppHandle,
        error_event: &'static str,
    ) -> Result<Self, String> {
        let stop_flag = Arc::new(AtomicBool::new(false));
        let run_loop = Arc::new(Mutex::new(None));
        let started = Arc::new(AtomicBool::new(false));
        let startup_error = Arc::new(Mutex::new(None::<String>));

        let stop_flag_thread = Arc::clone(&stop_flag);
        let run_loop_thread = Arc::clone(&run_loop);
        let started_thread = Arc::clone(&started);
        let startup_error_thread = Arc::clone(&startup_error);

        let app_for_thread = app.clone();
        let join_handle = thread::spawn(move || {
            let last_cmd_c = Arc::new(Mutex::new(None::<Instant>));
            let last_cmd_c_callback = Arc::clone(&last_cmd_c);
            let app_callback = app_for_thread.clone();

            eprintln!("hotkey_macos: starting event tap thread");

            let tap = CGEventTap::new(
                CGEventTapLocation::HID,
                CGEventTapPlacement::HeadInsertEventTap,
                CGEventTapOptions::Default,
                vec![CGEventType::KeyDown],
                move |_proxy, event_type, event| {
                    if !matches!(event_type, CGEventType::KeyDown) {
                        return CallbackResult::Keep;
                    }

                    if !event.get_flags().contains(CGEventFlags::CGEventFlagCommand) {
                        return CallbackResult::Keep;
                    }

                    let keycode = event.get_integer_value_field(EventField::KEYBOARD_EVENT_KEYCODE);
                    if keycode != i64::from(KeyCode::ANSI_C) {
                        return CallbackResult::Keep;
                    }

                    eprintln!("hotkey_macos: observed Cmd+C");

                    let now = Instant::now();
                    let mut guard = last_cmd_c_callback.lock().unwrap();
                    match *guard {
                        Some(previous) if now.duration_since(previous) <= Duration::from_millis(350) => {
                            *guard = None;
                            eprintln!("hotkey_macos: double Cmd+C detected");
                            eprintln!("hotkey_macos: requesting clipboard translation via Rust bridge");
                            if let Err(error) = crate::emit_clipboard_translation_request(&app_callback) {
                                eprintln!(
                                    "hotkey_macos: failed to request clipboard translation: {error}"
                                );
                            }
                            return CallbackResult::Drop;
                        }
                        _ => {
                            *guard = Some(now);
                        }
                    }

                    CallbackResult::Keep
                },
            );

            let Ok(tap) = tap else {
                eprintln!("hotkey_macos: failed to create event tap");
                *startup_error_thread.lock().unwrap() = Some(
                    "Global hotkey is unavailable. Grant Translator Accessibility and Input Monitoring permissions."
                        .to_string(),
                );
                started_thread.store(true, Ordering::Release);
                return;
            };

            let loop_source = match tap.mach_port().create_runloop_source(0) {
                Ok(source) => source,
                Err(_) => {
                    eprintln!("hotkey_macos: failed to create run loop source");
                    *startup_error_thread.lock().unwrap() =
                        Some("Failed to create macOS hotkey run loop source.".to_string());
                    started_thread.store(true, Ordering::Release);
                    return;
                }
            };

            let current_run_loop = CFRunLoop::get_current();
            current_run_loop.add_source(&loop_source, unsafe { kCFRunLoopCommonModes });
            tap.enable();
            eprintln!("hotkey_macos: event tap enabled");
            *run_loop_thread.lock().unwrap() = Some(current_run_loop.clone());
            started_thread.store(true, Ordering::Release);

            while !stop_flag_thread.load(Ordering::Acquire) {
                let _ = CFRunLoop::run_in_mode(
                    unsafe { kCFRunLoopDefaultMode },
                    Duration::from_millis(250),
                    true,
                );
            }

            current_run_loop.stop();
            eprintln!("hotkey_macos: event tap thread stopped");
        });

        let deadline = Instant::now() + Duration::from_secs(2);
        while !started.load(Ordering::Acquire) && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(20));
        }

        if let Some(error) = startup_error.lock().unwrap().clone() {
            eprintln!("hotkey_macos: startup error: {error}");
            let _ = app.emit(error_event, serde_json::json!({ "message": error.clone() }));
            stop_flag.store(true, Ordering::Release);
            let _ = join_handle.join();
            return Err(error);
        }

        eprintln!("hotkey_macos: listener started");

        Ok(Self {
            stop_flag,
            run_loop,
            join_handle: Some(join_handle),
        })
    }

    pub fn stop(mut self) {
        self.stop_flag.store(true, Ordering::Release);
        if let Some(run_loop) = self.run_loop.lock().unwrap().clone() {
            run_loop.stop();
        }
        if let Some(join_handle) = self.join_handle.take() {
            let _ = join_handle.join();
        }
    }
}
