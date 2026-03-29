// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|_app| {
            // dev 모드에서는 백엔드를 수동으로 실행
            // release 빌드 시 sidecar 자동 시작
            #[cfg(not(debug_assertions))]
            {
                use tauri_plugin_shell::ShellExt;
                let sidecar = _app.shell().sidecar("backend").expect("backend sidecar not found");
                let (_rx, _child) = sidecar.spawn().expect("failed to start backend");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
