#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Command, Stdio};

use serde::{Deserialize, Serialize};

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

    Err("No usable Python executable found. Expected .venv/bin/python, venv/bin/python, or python3 in PATH.".to_string())
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
        use std::io::Write;
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
fn save_config(payload: String) -> Result<String, String> {
    run_bridge("save-config", Some(&payload))
}

#[tauri::command]
fn translate(payload: String) -> Result<String, String> {
    run_bridge("translate", Some(&payload))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![backend_status, get_config, save_config, translate])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
