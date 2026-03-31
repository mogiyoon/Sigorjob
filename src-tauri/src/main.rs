// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use std::{net::TcpListener, process::exit};

use tauri::{Manager, RunEvent};
use tauri::AppHandle;
use tauri_plugin_shell::process::CommandChild;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

struct BackendSidecar(Mutex<Option<CommandChild>>);
fn pick_local_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    let port = listener.local_addr()?.port();
    drop(listener);
    Ok(port)
}

fn kill_sidecar(state: &BackendSidecar) {
    let child = {
        let mut guard = state.0.lock().expect("failed to lock backend sidecar state");
        guard.take()
    };
    if let Some(child) = child {
        let _ = child.kill();
    }
}

#[tauri::command]
fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    #[cfg(not(debug_assertions))]
    {
        #[allow(deprecated)]
        app.shell()
            .open(url, None)
            .map_err(|error| error.to_string())?;
        Ok(())
    }
    #[cfg(debug_assertions)]
    {
        let _ = app;
        let _ = url;
        Err("external open is only available in the packaged desktop app".into())
    }
}

fn main() {
    let local_api_port = pick_local_port().unwrap_or_else(|error| {
        eprintln!("failed to pick a local backend port: {error}");
        exit(1);
    });
    let local_api_base_url = format!("http://127.0.0.1:{local_api_port}");

    tauri::Builder::default()
        .manage(BackendSidecar(Mutex::new(None)))
        .plugin(tauri_plugin_shell::init())
        .setup(move |_app| {
            // dev 모드에서는 백엔드를 수동으로 실행
            // release 빌드 시 sidecar 자동 시작
            #[cfg(not(debug_assertions))]
            {
                let port = local_api_port;
                let sidecar = _app
                    .shell()
                    .sidecar("backend")
                    .expect("backend sidecar not found")
                    .args(["serve", "--host", "127.0.0.1", "--port", &port.to_string()])
                    .env("SIGORJOB_BACKEND_PORT", port.to_string())
                    .env("SIGORJOB_BACKEND_URL", format!("http://127.0.0.1:{port}"));
                let (_rx, child) = sidecar.spawn().expect("failed to start backend");
                let state = _app.state::<BackendSidecar>();
                *state.0.lock().expect("failed to lock backend sidecar state") = Some(child);
            }
            Ok(())
        })
        .on_page_load(move |webview, _payload| {
            let script = format!(
                "window.__SIGORJOB_LOCAL_API_URL = {base_url:?}; window.__SIGORJOB_LOCAL_API_PORT = {port};",
                base_url = local_api_base_url,
                port = local_api_port
            );
            let _ = webview.eval(script);
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<BackendSidecar>();
                kill_sidecar(state.inner());
            }
        })
        .invoke_handler(tauri::generate_handler![open_external_url])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
                let state = app.state::<BackendSidecar>();
                kill_sidecar(state.inner());
            }
        });
}
