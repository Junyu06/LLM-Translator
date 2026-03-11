#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, State, WindowEvent};

#[cfg(target_os = "macos")]
mod hotkey_macos;

const TRAY_OPEN_ID: &str = "tray_open";
const TRAY_TRANSLATE_CLIPBOARD_ID: &str = "tray_translate_clipboard";
const TRAY_QUIT_ID: &str = "tray_quit";
const EVENT_TRAY_OPENED: &str = "translator://tray-opened";
const EVENT_HOTKEY_ERROR: &str = "translator://hotkey-error";

struct RunningTranslation {
    job_id: u64,
    child: Arc<Mutex<Child>>,
}

struct AppState {
    quitting: AtomicBool,
    next_job_id: AtomicU64,
    canceled_job_id: AtomicU64,
    translation: Mutex<Option<RunningTranslation>>,
    translation_events: Mutex<HashMap<u64, Vec<Value>>>,
    hotkey_listener: Mutex<Option<HotkeyListener>>,
    frontend_ready: AtomicBool,
    pending_clipboard_triggers: AtomicU64,
}

#[cfg(target_os = "macos")]
type HotkeyListener = hotkey_macos::MacHotkeyListener;
#[cfg(not(target_os = "macos"))]
type HotkeyListener = ();

#[derive(Serialize)]
struct BackendStatus {
    state: String,
    python: Option<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct PythonHealth {
    status: String,
    python: String,
}

fn workspace_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(PathBuf::from)
        .ok_or_else(|| "Failed to resolve workspace root".to_string())
}

fn python_executable() -> Result<PathBuf, String> {
    let root = workspace_root()?;
    let candidates = if cfg!(target_os = "windows") {
        vec![
            root.join(".venv").join("Scripts").join("python.exe"),
            root.join("venv").join("Scripts").join("python.exe"),
            PathBuf::from("python"),
        ]
    } else {
        vec![
            root.join(".venv").join("bin").join("python"),
            root.join("venv").join("bin").join("python"),
            PathBuf::from("python3"),
            PathBuf::from("python"),
        ]
    };

    for candidate in candidates {
        if candidate.is_absolute() {
            if candidate.exists() {
                return Ok(candidate);
            }
        } else {
            return Ok(candidate);
        }
    }

    Err(
        "No usable Python executable found. Expected .venv/bin/python, venv/bin/python, or python3 in PATH."
            .to_string(),
    )
}

fn bridge_script() -> Result<PathBuf, String> {
    let root = workspace_root()?;
    let script = root.join("python_backend").join("bridge.py");
    if !script.exists() {
        return Err(format!("Python bridge not found: {}", script.display()));
    }
    Ok(script)
}

fn run_bridge(command: &str, input: Option<&str>) -> Result<String, String> {
    let root = workspace_root()?;
    let script = bridge_script()?;

    let mut process = Command::new(python_executable()?);
    process
        .current_dir(root)
        .arg(script)
        .arg(command)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = process
        .spawn()
        .map_err(|error| format!("Failed to spawn Python bridge: {error}"))?;

    if let Some(payload) = input {
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(payload.as_bytes())
                .map_err(|error| format!("Failed to write payload to Python bridge: {error}"))?;
        }
    }

    let output = child
        .wait_with_output()
        .map_err(|error| format!("Failed to read Python bridge output: {error}"))?;

    if output.status.success() {
        return String::from_utf8(output.stdout)
            .map_err(|error| format!("Python bridge stdout was not valid UTF-8: {error}"));
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Err(if !stdout.is_empty() {
        stdout
    } else if !stderr.is_empty() {
        stderr
    } else {
        format!("Python bridge exited with status {}", output.status)
    })
}

fn main_window(app: &AppHandle) -> Result<tauri::WebviewWindow, String> {
    app.get_webview_window("main")
        .ok_or_else(|| "Main window not found".to_string())
}

fn show_main_window(app: &AppHandle) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    app.set_dock_visibility(true)
        .map_err(|error| format!("Failed to show macOS dock icon: {error}"))?;

    #[cfg(target_os = "macos")]
    app.show()
        .map_err(|error| format!("Failed to show macOS app: {error}"))?;

    let window = main_window(app)?;
    if window.is_minimized().unwrap_or(false) {
        window
            .unminimize()
            .map_err(|error| format!("Failed to restore minimized window: {error}"))?;
    }
    window
        .show()
        .map_err(|error| format!("Failed to show main window: {error}"))?;
    window
        .set_focus()
        .map_err(|error| format!("Failed to focus main window: {error}"))?;
    Ok(())
}

fn should_minimize_to_tray() -> bool {
    run_bridge("get-config", None)
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|value| value.get("minimize_to_tray").and_then(Value::as_bool))
        .unwrap_or(true)
}

fn hotkey_enabled() -> bool {
    run_bridge("get-config", None)
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|value| value.get("hotkey_enabled").and_then(Value::as_bool))
        .unwrap_or(true)
}

fn read_clipboard_text_impl() -> Result<String, String> {
    if cfg!(target_os = "macos") {
        let output = Command::new("/usr/bin/pbpaste")
            .output()
            .map_err(|error| format!("Failed to read clipboard via pbpaste: {error}"))?;
        if output.status.success() {
            return String::from_utf8(output.stdout)
                .map_err(|error| format!("Clipboard text was not valid UTF-8: {error}"));
        }
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            "pbpaste exited unsuccessfully".to_string()
        } else {
            stderr
        });
    }

    if cfg!(target_os = "windows") {
        let output = Command::new("powershell")
            .args(["-NoProfile", "-Command", "Get-Clipboard -Raw"])
            .output()
            .map_err(|error| format!("Failed to read clipboard via PowerShell: {error}"))?;
        if output.status.success() {
            return String::from_utf8(output.stdout)
                .map_err(|error| format!("Clipboard text was not valid UTF-8: {error}"));
        }
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            "PowerShell Get-Clipboard exited unsuccessfully".to_string()
        } else {
            stderr
        });
    }

    Err("Clipboard text commands are implemented only for macOS and Windows.".to_string())
}

fn write_clipboard_text_impl(payload: &str) -> Result<(), String> {
    if cfg!(target_os = "macos") {
        let mut child = Command::new("/usr/bin/pbcopy")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("Failed to launch pbcopy: {error}"))?;
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(payload.as_bytes())
                .map_err(|error| format!("Failed to write clipboard payload: {error}"))?;
        }
        let output = child
            .wait_with_output()
            .map_err(|error| format!("Failed to finish pbcopy: {error}"))?;
        if output.status.success() {
            return Ok(());
        }
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            "pbcopy exited unsuccessfully".to_string()
        } else {
            stderr
        });
    }

    if cfg!(target_os = "windows") {
        let mut child = Command::new("cmd")
            .args(["/C", "clip"])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("Failed to launch clip.exe: {error}"))?;
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(payload.as_bytes())
                .map_err(|error| format!("Failed to write clipboard payload: {error}"))?;
        }
        let output = child
            .wait_with_output()
            .map_err(|error| format!("Failed to finish clip.exe: {error}"))?;
        if output.status.success() {
            return Ok(());
        }
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            "clip.exe exited unsuccessfully".to_string()
        } else {
            stderr
        });
    }

    Err("Clipboard write commands are implemented only for macOS and Windows.".to_string())
}

pub(crate) fn emit_clipboard_translation_request(app: &AppHandle) -> Result<(), String> {
    eprintln!("main: request clipboard translation");

    let state = app.state::<AppState>();
    if !state.frontend_ready.load(Ordering::Acquire) {
        let pending = state
            .pending_clipboard_triggers
            .fetch_add(1, Ordering::AcqRel)
            + 1;
        eprintln!("main: frontend not ready yet; queued trigger (pending={pending})");
        // Best effort: still show the window so the webview initializes.
        let _ = show_main_window(app);
        return Ok(());
    }

    let window = main_window(app)?;

    // Let the source app finish the second Cmd+C and update the clipboard before we steal focus.
    std::thread::sleep(std::time::Duration::from_millis(140));
    let clipboard_text = read_clipboard_text_impl().ok();

    // Hidden windows can still accept eval, so delay bringing the app forward until after the frontend
    // has started reading the clipboard.
    let mut last_error: Option<String> = None;
    for attempt in 1..=6 {
        let delay_ms = match attempt {
            1 => 0,
            2 => 50,
            3 => 90,
            4 => 140,
            5 => 220,
            _ => 320,
        };
        if delay_ms > 0 {
            std::thread::sleep(std::time::Duration::from_millis(delay_ms));
        }

        let payload = clipboard_text
            .as_ref()
            .map(|text| serde_json::to_string(text))
            .transpose()
            .map_err(|error| format!("Failed to serialize clipboard text: {error}"))?;
        let script = match payload {
            Some(text) => format!(
                r#"
                  try {{
                    const ok = typeof window.__translatorTriggerClipboardTranslation === 'function';
                    console.log('[translator] hotkey eval attempt: bridge=', ok);
                    if (ok) window.__translatorTriggerClipboardTranslation({text});
                  }} catch (e) {{
                    console.log('[translator] hotkey eval error', e);
                  }}
                "#
            ),
            None => r#"
                  try {
                    const ok = typeof window.__translatorTriggerClipboardTranslation === 'function';
                    console.log('[translator] hotkey eval attempt: bridge=', ok);
                    if (ok) window.__translatorTriggerClipboardTranslation();
                  } catch (e) {
                    console.log('[translator] hotkey eval error', e);
                  }
                "#
            .to_string(),
        };

        match window.eval(&script) {
            Ok(()) => {
                eprintln!("main: clipboard trigger eval sent (attempt={attempt})");
                show_main_window(app)?;
                return Ok(());
            }
            Err(error) => {
                let message = format!("{error}");
                eprintln!(
                    "main: clipboard trigger eval failed (attempt={attempt}): {message}"
                );
                last_error = Some(message);
            }
        }
    }

    // If eval keeps failing, queue it so it can be retried after the frontend reports ready again.
    let pending = state
        .pending_clipboard_triggers
        .fetch_add(1, Ordering::AcqRel)
        + 1;
    eprintln!("main: queued clipboard trigger after eval failures (pending={pending})");
    Err(last_error.unwrap_or_else(|| "Failed to eval clipboard trigger.".to_string()))
}

fn flush_pending_clipboard_triggers(app: &AppHandle) {
    let state = app.state::<AppState>();
    if !state.frontend_ready.load(Ordering::Acquire) {
        return;
    }

    let pending = state.pending_clipboard_triggers.swap(0, Ordering::AcqRel);
    if pending == 0 {
        return;
    }
    eprintln!("main: flushing queued clipboard triggers (count={pending})");
    for _ in 0..pending {
        if let Err(error) = emit_clipboard_translation_request(app) {
            eprintln!("main: failed to flush clipboard trigger: {error}");
            break;
        }
    }
}

#[tauri::command]
fn frontend_ready(app: AppHandle, state: State<AppState>) -> Result<(), String> {
    eprintln!("main: frontend reported ready");
    state.frontend_ready.store(true, Ordering::Release);
    flush_pending_clipboard_triggers(&app);
    Ok(())
}

fn build_tray(app: &AppHandle) -> Result<(), String> {
    let open_item =
        MenuItem::with_id(app, TRAY_OPEN_ID, "Open Translator", true, None::<&str>)
            .map_err(|error| format!("Failed to create tray menu item: {error}"))?;
    let translate_clipboard_item = MenuItem::with_id(
        app,
        TRAY_TRANSLATE_CLIPBOARD_ID,
        "Translate Clipboard",
        true,
        None::<&str>,
    )
    .map_err(|error| format!("Failed to create tray menu item: {error}"))?;
    let quit_item = MenuItem::with_id(app, TRAY_QUIT_ID, "Quit", true, None::<&str>)
        .map_err(|error| format!("Failed to create tray menu item: {error}"))?;
    let separator = PredefinedMenuItem::separator(app)
        .map_err(|error| format!("Failed to create tray separator: {error}"))?;

    let menu = Menu::with_items(
        app,
        &[&open_item, &translate_clipboard_item, &separator, &quit_item],
    )
    .map_err(|error| format!("Failed to create tray menu: {error}"))?;

    let mut builder = TrayIconBuilder::with_id("translator-tray").menu(&menu);
    if let Some(icon) = app.default_window_icon().cloned() {
        builder = builder.icon(icon);
    }

    builder
        .show_menu_on_left_click(false)
        .build(app)
        .map_err(|error| format!("Failed to build tray icon: {error}"))?;

    Ok(())
}

fn cancel_running_translation(
    _app: &AppHandle,
    state: &AppState,
    expected_job_id: Option<u64>,
    emit_event: bool,
) -> Result<Option<u64>, String> {
    let running = {
        let mut guard = state.translation.lock().unwrap();
        if let Some(current) = guard.as_ref() {
            if expected_job_id.is_none() || expected_job_id == Some(current.job_id) {
                guard.take()
            } else {
                None
            }
        } else {
            None
        }
    };

    if let Some(running) = running {
        state.canceled_job_id.store(running.job_id, Ordering::Relaxed);
        let mut child = running.child.lock().unwrap();
        let _ = child.kill();
        let _ = child.wait();

        if emit_event {
            enqueue_translation_event(
                state,
                running.job_id,
                json!({
                    "job_id": running.job_id,
                    "event": "canceled",
                }),
            );
        }

        return Ok(Some(running.job_id));
    }

    Ok(None)
}

fn enqueue_translation_event(state: &AppState, job_id: u64, payload: Value) {
    let mut guard = state.translation_events.lock().unwrap();
    guard.entry(job_id).or_default().push(payload);
}

fn stop_hotkey_listener(state: &AppState) {
    let running = {
        let mut guard = state.hotkey_listener.lock().unwrap();
        guard.take()
    };

    if let Some(child) = running {
        #[cfg(target_os = "macos")]
        child.stop();
    }
}

fn spawn_hotkey_listener(app: &AppHandle, state: &AppState) -> Result<(), String> {
    stop_hotkey_listener(state);

    if !hotkey_enabled() {
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        eprintln!("main: starting native macOS hotkey listener");
        let listener = hotkey_macos::MacHotkeyListener::start(app.clone(), EVENT_HOTKEY_ERROR)?;
        let mut guard = state.hotkey_listener.lock().unwrap();
        *guard = Some(listener);
        eprintln!("main: native macOS hotkey listener ready");
        return Ok(());
    }

    #[cfg(not(target_os = "macos"))]
    {
        app.emit(
            EVENT_HOTKEY_ERROR,
            json!({ "message": "Native global hotkey is not implemented on this platform yet." }),
        )
        .map_err(|error| format!("Failed to emit hotkey platform message: {error}"))?;
        Ok(())
    }
}

fn spawn_translation_stream(app: &AppHandle, payload: &str, state: &AppState) -> Result<u64, String> {
    let _ = cancel_running_translation(app, state, None, false)?;

    let root = workspace_root()?;
    let script = bridge_script()?;
    let job_id = state.next_job_id.fetch_add(1, Ordering::Relaxed) + 1;

    let mut process = Command::new(python_executable()?);
    process
        .current_dir(root)
        .arg(script)
        .arg("translate-stream")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());

    let mut child = process
        .spawn()
        .map_err(|error| format!("Failed to spawn streaming translation bridge: {error}"))?;

    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(payload.as_bytes())
            .map_err(|error| format!("Failed to send translation payload: {error}"))?;
    }

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Streaming translation bridge did not provide stdout".to_string())?;
    let child = Arc::new(Mutex::new(child));

    {
        let mut guard = state.translation.lock().unwrap();
        *guard = Some(RunningTranslation {
            job_id,
            child: Arc::clone(&child),
        });
    }
    {
        let mut guard = state.translation_events.lock().unwrap();
        guard.insert(job_id, Vec::new());
    }

    let app_handle = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else {
                enqueue_translation_event(
                    &app_handle.state::<AppState>(),
                    job_id,
                    json!({
                        "job_id": job_id,
                        "event": "error",
                        "message": "Failed to read translation progress output.",
                    }),
                );
                break;
            };

            if line.trim().is_empty() {
                continue;
            }

            match serde_json::from_str::<Value>(&line) {
                Ok(mut payload) => {
                    if let Some(object) = payload.as_object_mut() {
                        if !object.contains_key("event") {
                            if let Some(message) = object.get("error").cloned() {
                                object.insert("event".into(), Value::from("error"));
                                object.insert("message".into(), message);
                            }
                        }
                        object.insert("job_id".into(), Value::from(job_id));
                    }
                    enqueue_translation_event(&app_handle.state::<AppState>(), job_id, payload);
                }
                Err(error) => {
                    enqueue_translation_event(
                        &app_handle.state::<AppState>(),
                        job_id,
                        json!({
                            "job_id": job_id,
                            "event": "error",
                            "message": format!("Invalid translation progress payload: {error}"),
                        }),
                    );
                }
            }
        }

        let canceled_job_id = app_handle
            .state::<AppState>()
            .canceled_job_id
            .load(Ordering::Relaxed);
        {
            let app_state = app_handle.state::<AppState>();
            let mut guard = app_state.translation.lock().unwrap();
            if guard.as_ref().map(|running| running.job_id) == Some(job_id) {
                guard.take();
            }
        }

        let _ = child.lock().unwrap().wait();

        if canceled_job_id == job_id {
            enqueue_translation_event(
                &app_handle.state::<AppState>(),
                job_id,
                json!({
                    "job_id": job_id,
                    "event": "canceled",
                }),
            );
        }
    });

    Ok(job_id)
}

#[tauri::command]
fn backend_status() -> BackendStatus {
    match run_bridge("health", None) {
        Ok(raw) => match serde_json::from_str::<PythonHealth>(&raw) {
            Ok(result) if result.status == "ok" => BackendStatus {
                state: "running".to_string(),
                python: Some(result.python),
                error: None,
            },
            Ok(result) => BackendStatus {
                state: "stopped".to_string(),
                python: Some(result.python),
                error: Some(format!("Unexpected health status: {}", result.status)),
            },
            Err(error) => BackendStatus {
                state: "stopped".to_string(),
                python: None,
                error: Some(format!("Failed to decode backend health: {error}")),
            },
        },
        Err(error) => BackendStatus {
            state: "stopped".to_string(),
            python: None,
            error: Some(error),
        },
    }
}

#[tauri::command]
fn get_config() -> Result<String, String> {
    run_bridge("get-config", None)
}

#[tauri::command]
fn save_config(app: AppHandle, payload: String, state: State<AppState>) -> Result<String, String> {
    let result = run_bridge("save-config", Some(&payload))?;
    spawn_hotkey_listener(&app, &state)?;
    Ok(result)
}

#[tauri::command]
fn sync_hotkey_listener(app: AppHandle, state: State<AppState>) -> Result<(), String> {
    spawn_hotkey_listener(&app, &state)
}

#[tauri::command]
fn translate(payload: String) -> Result<String, String> {
    run_bridge("translate", Some(&payload))
}

#[tauri::command]
fn start_translation_stream(
    app: AppHandle,
    payload: String,
    state: State<AppState>,
) -> Result<u64, String> {
    spawn_translation_stream(&app, &payload, &state)
}

#[tauri::command]
fn take_translation_events(job_id: u64, state: State<AppState>) -> Result<Vec<Value>, String> {
    let mut guard = state.translation_events.lock().unwrap();
    let Some(buffer) = guard.get_mut(&job_id) else {
        return Ok(Vec::new());
    };

    let drained = std::mem::take(buffer);
    let should_remove = drained.iter().any(|event| {
        matches!(
            event.get("event").and_then(Value::as_str),
            Some("completed" | "canceled" | "error")
        )
    });

    if should_remove {
        guard.remove(&job_id);
    }

    Ok(drained)
}

#[tauri::command]
fn cancel_translation(app: AppHandle, job_id: Option<u64>, state: State<AppState>) -> Result<bool, String> {
    Ok(cancel_running_translation(&app, &state, job_id, true)?.is_some())
}

#[tauri::command]
fn show_main_window_command(app: AppHandle) -> Result<(), String> {
    show_main_window(&app)
}

#[tauri::command]
fn read_clipboard_text() -> Result<String, String> {
    read_clipboard_text_impl()
}

#[tauri::command]
fn write_clipboard_text(payload: String) -> Result<(), String> {
    write_clipboard_text_impl(&payload)
}

#[tauri::command]
fn run_clipboard_ocr() -> Result<String, String> {
    run_bridge("ocr-clipboard", None)
}

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            quitting: AtomicBool::new(false),
            next_job_id: AtomicU64::new(0),
            canceled_job_id: AtomicU64::new(0),
            translation: Mutex::new(None),
            translation_events: Mutex::new(HashMap::new()),
            hotkey_listener: Mutex::new(None),
            frontend_ready: AtomicBool::new(false),
            pending_clipboard_triggers: AtomicU64::new(0),
        })
        .setup(|app| {
            build_tray(&app.handle())?;
            let _ = spawn_hotkey_listener(&app.handle(), &app.state::<AppState>());
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            TRAY_OPEN_ID => {
                let _ = show_main_window(app);
                let _ = app.emit(EVENT_TRAY_OPENED, ());
            }
            TRAY_TRANSLATE_CLIPBOARD_ID => {
                let _ = emit_clipboard_translation_request(app);
            }
            TRAY_QUIT_ID => {
                app.state::<AppState>()
                    .quitting
                    .store(true, Ordering::Relaxed);
                stop_hotkey_listener(&app.state::<AppState>());
                let _ = cancel_running_translation(app, &app.state::<AppState>(), None, false);
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                let _ = show_main_window(&app);
                let _ = app.emit(EVENT_TRAY_OPENED, ());
            }
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != "main" {
                    return;
                }

                if window
                    .app_handle()
                    .state::<AppState>()
                    .quitting
                    .load(Ordering::Relaxed)
                {
                    return;
                }

                if should_minimize_to_tray() {
                    api.prevent_close();
                    let _ = window.hide();
                    #[cfg(target_os = "macos")]
                    {
                        let app = window.app_handle();
                        let _ = app.set_dock_visibility(false);
                        let _ = app.hide();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            backend_status,
            get_config,
            save_config,
            sync_hotkey_listener,
            translate,
            start_translation_stream,
            take_translation_events,
            cancel_translation,
            show_main_window_command,
            read_clipboard_text,
            write_clipboard_text,
            run_clipboard_ocr,
            frontend_ready
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
