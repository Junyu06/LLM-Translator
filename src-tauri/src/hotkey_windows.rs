use std::io::{BufRead, BufReader};
use std::process::{Child, Stdio};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

const EVENT_HOTKEY_ERROR: &str = "translator://hotkey-error";

pub struct WindowsHotkeyListener {
    child: Arc<Mutex<Option<Child>>>,
    join_handle: Option<JoinHandle<()>>,
}

impl WindowsHotkeyListener {
    pub fn start(app: AppHandle) -> Result<Self, String> {
        let mut process = crate::bridge_process(&app, "hotkey-listener")?;
        process
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = process
            .spawn()
            .map_err(|error| format!("Failed to spawn Windows hotkey listener: {error}"))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Windows hotkey listener did not provide stdout.".to_string())?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| "Windows hotkey listener did not provide stderr.".to_string())?;

        let child = Arc::new(Mutex::new(Some(child)));
        let child_for_thread = Arc::clone(&child);
        let app_for_thread = app.clone();

        let join_handle = thread::spawn(move || {
            let stderr_thread = thread::spawn(move || {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    if !line.trim().is_empty() {
                        eprintln!("hotkey_windows: {line}");
                    }
                }
            });

            for line in BufReader::new(stdout).lines() {
                let Ok(line) = line else {
                    let _ = app_for_thread.emit(
                        EVENT_HOTKEY_ERROR,
                        json!({ "message": "Failed to read Windows hotkey listener output." }),
                    );
                    break;
                };

                if line.trim().is_empty() {
                    continue;
                }

                match serde_json::from_str::<Value>(&line) {
                    Ok(payload) if payload.get("event").and_then(Value::as_str) == Some("trigger") => {
                        if let Err(error) = crate::emit_clipboard_translation_request(&app_for_thread) {
                            eprintln!("hotkey_windows: failed to trigger clipboard translation: {error}");
                        }
                    }
                    Ok(payload) if payload.get("event").and_then(Value::as_str) == Some("error") => {
                        let message = payload
                            .get("message")
                            .and_then(Value::as_str)
                            .or_else(|| payload.get("error").and_then(Value::as_str))
                            .unwrap_or("Windows hotkey listener failed.");
                        let _ = app_for_thread.emit(EVENT_HOTKEY_ERROR, json!({ "message": message }));
                        eprintln!("hotkey_windows: {message}");
                    }
                    Ok(_) => {}
                    Err(error) => {
                        eprintln!("hotkey_windows: invalid listener payload: {error}");
                    }
                }
            }

            if let Some(mut child) = child_for_thread.lock().unwrap().take() {
                let _ = child.wait();
            }
            let _ = stderr_thread.join();
        });

        Ok(Self {
            child,
            join_handle: Some(join_handle),
        })
    }

    pub fn stop(mut self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        if let Some(join_handle) = self.join_handle.take() {
            let _ = join_handle.join();
        }
    }
}
