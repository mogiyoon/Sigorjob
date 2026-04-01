// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(not(debug_assertions))]
use std::env;

#[cfg(not(debug_assertions))]
use std::fs::{self, OpenOptions};

#[cfg(not(debug_assertions))]
use std::io::{Read, Write};

#[cfg(not(debug_assertions))]
use std::net::{TcpListener, TcpStream};

#[cfg(not(debug_assertions))]
use std::path::PathBuf;

#[cfg(not(debug_assertions))]
use std::process::Command;

use std::sync::Mutex;

#[cfg(not(debug_assertions))]
use std::sync::Arc;

#[cfg(not(debug_assertions))]
use std::thread;

#[cfg(not(debug_assertions))]
use std::time::{Duration, Instant};

#[cfg(not(debug_assertions))]
use tauri::{Manager, RunEvent};

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::process::{CommandChild, CommandEvent};

#[cfg(not(debug_assertions))]
struct BackendChildState(Mutex<Option<CommandChild>>);

#[cfg(not(debug_assertions))]
struct BackendStartupLogState(Arc<Mutex<Vec<String>>>);

struct LocalApiUrlState(Mutex<String>);

#[cfg(not(debug_assertions))]
struct BackendStartupLogPathState(Mutex<String>);

#[cfg(not(debug_assertions))]
struct BackendStartupErrorState(Mutex<String>);

#[cfg(not(debug_assertions))]
fn app_lock_path() -> PathBuf {
    env::temp_dir().join("sigorjob-desktop.lock")
}

#[cfg(not(debug_assertions))]
fn startup_log_path() -> PathBuf {
    env::temp_dir().join("sigorjob-startup.log")
}

#[cfg(not(debug_assertions))]
fn reset_startup_log_file() -> PathBuf {
    let path = startup_log_path();
    let _ = fs::write(&path, b"");
    path
}

#[cfg(not(debug_assertions))]
fn append_startup_log_file(path: &str, line: &str) {
    if path.is_empty() {
        return;
    }
    if let Ok(mut file) = OpenOptions::new().append(true).create(true).open(path) {
        let _ = writeln!(file, "{line}");
    }
}

#[cfg(not(debug_assertions))]
fn pid_is_running(pid: &str) -> bool {
    Command::new("kill")
        .args(["-0", pid])
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

#[cfg(not(debug_assertions))]
fn acquire_app_lock() -> bool {
    let lock_path = app_lock_path();
    if let Ok(existing_pid) = fs::read_to_string(&lock_path) {
        let pid = existing_pid.trim();
        if !pid.is_empty() && pid_is_running(pid) {
            return false;
        }
        let _ = fs::remove_file(&lock_path);
    }

    match OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&lock_path)
    {
        Ok(mut file) => file
            .write_all(std::process::id().to_string().as_bytes())
            .is_ok(),
        Err(_) => false,
    }
}

#[cfg(not(debug_assertions))]
fn release_app_lock() {
    let _ = fs::remove_file(app_lock_path());
}

#[cfg(not(debug_assertions))]
fn push_startup_log(logs: &Arc<Mutex<Vec<String>>>, log_path: &str, message: impl Into<String>) {
    let line = message.into();
    if let Ok(mut guard) = logs.lock() {
        guard.push(line.clone());
        if guard.len() > 40 {
            let overflow = guard.len() - 40;
            guard.drain(0..overflow);
        }
    }
    append_startup_log_file(log_path, &line);
}

#[cfg(not(debug_assertions))]
fn startup_log_snapshot(logs: &Arc<Mutex<Vec<String>>>) -> String {
    logs.lock()
        .map(|guard| guard.join(" | "))
        .unwrap_or_else(|_| "startup log unavailable".to_string())
}

#[cfg(not(debug_assertions))]
fn bundled_binary_path(name: &str) -> Option<PathBuf> {
    let executable = env::current_exe().ok()?;
    let executable_dir = executable.parent()?;
    Some(executable_dir.join(name))
}

#[cfg(not(debug_assertions))]
fn cleanup_bundled_processes() {
    let current_pid = std::process::id().to_string();
    for binary_name in ["backend", "cloudflared"] {
        let Some(binary_path) = bundled_binary_path(binary_name) else {
            continue;
        };

        let pattern = binary_path.to_string_lossy().to_string();
        let pgrep_output = Command::new("pgrep").args(["-f", &pattern]).output();
        let Ok(output) = pgrep_output else {
            continue;
        };
        if !output.status.success() {
            continue;
        }

        let pids: Vec<String> = String::from_utf8_lossy(&output.stdout)
            .lines()
            .map(str::trim)
            .filter(|pid| !pid.is_empty() && *pid != current_pid)
            .map(str::to_string)
            .collect();

        for pid in &pids {
            let _ = Command::new("kill").args(["-TERM", pid]).status();
        }

        let deadline = Instant::now() + Duration::from_secs(3);
        while Instant::now() < deadline {
            let any_alive = pids.iter().any(|pid| pid_is_running(pid));
            if !any_alive {
                break;
            }
            thread::sleep(Duration::from_millis(150));
        }

        for pid in &pids {
            if pid_is_running(pid) {
                let _ = Command::new("kill").args(["-KILL", pid]).status();
            }
        }
    }
}

#[cfg(not(debug_assertions))]
fn select_backend_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0")
        .map_err(|error| format!("failed to reserve local backend port: {error}"))?;
    let port = listener
        .local_addr()
        .map_err(|error| format!("failed to inspect reserved local backend port: {error}"))?
        .port();
    drop(listener);
    Ok(port)
}

#[cfg(not(debug_assertions))]
fn stop_backend_sidecar() {
    cleanup_bundled_processes();
    release_app_lock();
}

#[cfg(debug_assertions)]
#[allow(dead_code)]
fn stop_backend_sidecar() {
}

#[cfg(not(debug_assertions))]
fn wait_for_backend_ready(
    port: u16,
    timeout: Duration,
    logs: &Arc<Mutex<Vec<String>>>,
    log_path: &str,
) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    let host = format!("127.0.0.1:{port}");
    let request = format!("GET /setup/status HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    while Instant::now() < deadline {
        if let Ok(mut stream) = TcpStream::connect(&host) {
            let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
            let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
            if stream.write_all(request.as_bytes()).is_ok() {
                let mut response = String::new();
                if stream.read_to_string(&mut response).is_ok()
                    && response.starts_with("HTTP/1.1 200")
                {
                    push_startup_log(logs, log_path, format!("backend ready on port {port}: /setup/status returned 200"));
                    return Ok(());
                }
                push_startup_log(
                    logs,
                    log_path,
                    format!("backend probe connected on port {port} but /setup/status was not 200"),
                );
            }
        }
        thread::sleep(Duration::from_millis(250));
    }

    Err(format!(
        "backend did not become ready in time; recent startup logs: {}",
        startup_log_snapshot(logs)
    ))
}

#[cfg(not(debug_assertions))]
fn launch_backend_sidecar(app: &tauri::App) -> Result<(), String> {
    cleanup_bundled_processes();
    let startup_logs = app.state::<BackendStartupLogState>().0.clone();
    let startup_log_path_buf = reset_startup_log_file();
    let startup_log_path = startup_log_path_buf.to_string_lossy().to_string();
    {
        let log_path_state = app.state::<BackendStartupLogPathState>();
        let mut guard = log_path_state
            .0
            .lock()
            .map_err(|_| "startup log path mutex poisoned".to_string())?;
        *guard = startup_log_path.clone();
    }
    {
        let error_state = app.state::<BackendStartupErrorState>();
        let mut guard = error_state
            .0
            .lock()
            .map_err(|_| "startup error mutex poisoned".to_string())?;
        guard.clear();
    }
    if let Ok(mut guard) = startup_logs.lock() {
        guard.clear();
    }
    push_startup_log(&startup_logs, &startup_log_path, "startup begin");
    push_startup_log(&startup_logs, &startup_log_path, "cleanup complete");
    let state = app.state::<BackendChildState>();
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "backend child mutex poisoned".to_string())?;
    if let Some(child) = guard.take() {
        let _ = child.kill();
    }

    let port = select_backend_port()?;
    let local_api_url = format!("http://127.0.0.1:{port}");
    {
        let local_api_url_state = app.state::<LocalApiUrlState>();
        let mut local_api_url_guard = local_api_url_state
            .0
            .lock()
            .map_err(|_| "local api url mutex poisoned".to_string())?;
        *local_api_url_guard = local_api_url.clone();
    }
    push_startup_log(&startup_logs, &startup_log_path, format!("selected backend port {port}"));

    let sidecar = app
        .shell()
        .sidecar("backend")
        .map_err(|_| "backend sidecar not found".to_string())?;
    let (mut rx, child) = sidecar
        .args(["serve", "--port", &port.to_string()])
        .env("SIGORJOB_BACKEND_PORT", port.to_string())
        .env("SIGORJOB_LOCAL_API_URL", local_api_url.clone())
        .spawn()
        .map_err(|error| format!("failed to start backend: {error}"))?;
    push_startup_log(
        &startup_logs,
        &startup_log_path,
        format!("backend sidecar spawned (pid={}) on port {port}", child.pid()),
    );

    let startup_logs_for_thread = startup_logs.clone();
    let startup_log_path_for_thread = startup_log_path.clone();
    thread::spawn(move || {
        while let Some(event) = rx.blocking_recv() {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        push_startup_log(&startup_logs_for_thread, &startup_log_path_for_thread, format!("stdout: {text}"));
                    }
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line).trim().to_string();
                    if !text.is_empty() {
                        push_startup_log(&startup_logs_for_thread, &startup_log_path_for_thread, format!("stderr: {text}"));
                    }
                }
                CommandEvent::Error(error) => {
                    push_startup_log(&startup_logs_for_thread, &startup_log_path_for_thread, format!("shell error: {error}"));
                }
                CommandEvent::Terminated(payload) => {
                    push_startup_log(
                        &startup_logs_for_thread,
                        &startup_log_path_for_thread,
                        format!(
                            "backend terminated early (code={:?}, signal={:?})",
                            payload.code, payload.signal
                        ),
                    );
                }
                _ => {}
            }
        }
    });

    *guard = Some(child);
    drop(guard);

    if let Err(error) = wait_for_backend_ready(port, Duration::from_secs(15), &startup_logs, &startup_log_path) {
        if let Ok(mut guard) = app.state::<BackendStartupErrorState>().0.lock() {
            *guard = error.clone();
        }
        push_startup_log(&startup_logs, &startup_log_path, format!("startup failed: {error}"));
        stop_backend_sidecar();
        return Err(error);
    }

    push_startup_log(&startup_logs, &startup_log_path, "startup succeeded");
    Ok(())
}

#[tauri::command]
fn open_external_url(app_handle: tauri::AppHandle, url: String) -> Result<(), String> {
    #[cfg(not(debug_assertions))]
    {
        return app_handle
            .shell()
            .open(&url, None)
            .map_err(|error| error.to_string());
    }

    #[cfg(debug_assertions)]
    {
        let _ = app_handle;
        let _ = url;
        Ok(())
    }
}

#[tauri::command]
fn get_local_api_url(app_handle: tauri::AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    {
        let state = app_handle.state::<LocalApiUrlState>();
        let guard = state
            .0
            .lock()
            .map_err(|_| "local api url mutex poisoned".to_string())?;
        if guard.is_empty() {
            return Err("local api url is not ready".to_string());
        }
        return Ok(guard.clone());
    }

    #[cfg(debug_assertions)]
    {
        let _ = app_handle;
        Ok("http://127.0.0.1:8000".to_string())
    }
}

#[tauri::command]
fn get_backend_startup_error(app_handle: tauri::AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    {
        let state = app_handle.state::<BackendStartupErrorState>();
        let guard = state
            .0
            .lock()
            .map_err(|_| "startup error mutex poisoned".to_string())?;
        return Ok(guard.clone());
    }

    #[cfg(debug_assertions)]
    {
        let _ = app_handle;
        Ok(String::new())
    }
}

#[tauri::command]
fn get_backend_startup_log_path(app_handle: tauri::AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    {
        let state = app_handle.state::<BackendStartupLogPathState>();
        let guard = state
            .0
            .lock()
            .map_err(|_| "startup log path mutex poisoned".to_string())?;
        return Ok(guard.clone());
    }

    #[cfg(debug_assertions)]
    {
        let _ = app_handle;
        Ok(String::new())
    }
}

fn main() {
    let builder = tauri::Builder::default().plugin(tauri_plugin_shell::init());

    #[cfg(not(debug_assertions))]
    let builder = builder.manage(BackendChildState(Mutex::new(None)));

    #[cfg(not(debug_assertions))]
    let builder = builder.manage(BackendStartupLogState(Arc::new(Mutex::new(Vec::new()))));

    #[cfg(not(debug_assertions))]
    let builder = builder.manage(LocalApiUrlState(Mutex::new(String::new())));

    #[cfg(not(debug_assertions))]
    let builder = builder.manage(BackendStartupLogPathState(Mutex::new(String::new())));

    #[cfg(not(debug_assertions))]
    let builder = builder.manage(BackendStartupErrorState(Mutex::new(String::new())));

    #[cfg(debug_assertions)]
    let builder = builder.manage(LocalApiUrlState(Mutex::new(
        "http://127.0.0.1:8000".to_string(),
    )));

    builder
        .setup(|_app| {
            #[cfg(not(debug_assertions))]
            {
                if !acquire_app_lock() {
                    _app.handle().exit(0);
                    return Ok(());
                }
                if let Err(error) = launch_backend_sidecar(_app) {
                    eprintln!("Sigorjob startup warning: {error}");
                }
            }
            Ok(())
        })
        .on_page_load(|window, _payload| {
            #[cfg(not(debug_assertions))]
            {
                if let Ok(local_api_url) = get_local_api_url(window.app_handle().clone()) {
                    let script = format!(
                        "window.__SIGORJOB_LOCAL_API_URL = {};",
                        serde_json::to_string(&local_api_url).unwrap_or_else(|_| "\"\"".to_string())
                    );
                    let _ = window.eval(&script);
                }
                if let Ok(startup_error) = get_backend_startup_error(window.app_handle().clone()) {
                    let script = format!(
                        "window.__SIGORJOB_STARTUP_ERROR = {};",
                        serde_json::to_string(&startup_error).unwrap_or_else(|_| "\"\"".to_string())
                    );
                    let _ = window.eval(&script);
                }
                if let Ok(startup_log_path) = get_backend_startup_log_path(window.app_handle().clone()) {
                    let script = format!(
                        "window.__SIGORJOB_STARTUP_LOG_PATH = {};",
                        serde_json::to_string(&startup_log_path).unwrap_or_else(|_| "\"\"".to_string())
                    );
                    let _ = window.eval(&script);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            open_external_url,
            get_local_api_url,
            get_backend_startup_error,
            get_backend_startup_log_path
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, _event| {
            #[cfg(not(debug_assertions))]
            match _event {
                RunEvent::ExitRequested { .. } | RunEvent::Exit => {
                    stop_backend_sidecar();
                }
                _ => {}
            }
        });
}
