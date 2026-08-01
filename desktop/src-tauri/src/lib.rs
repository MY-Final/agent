use std::net::TcpListener;
use std::process::{Child, Command as StdCommand, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};

/// 侧车后端运行状态：端口与子进程句柄。
struct BackendState {
    port: Option<u16>,
    child: Option<Child>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            port: None,
            child: None,
        }
    }
}

/// 在 18000-18019 段探测一个可绑定的端口。
fn find_free_port() -> Option<u16> {
    (18000..18020).find(|port| TcpListener::bind(("127.0.0.1", *port)).is_ok())
}

/// 通过原始 TCP 探测后端 /health，避免引入额外 HTTP 依赖。
async fn health_ok(port: u16) -> bool {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};

    let Ok(mut stream) = tokio::net::TcpStream::connect(("127.0.0.1", port)).await else {
        return false;
    };
    let request = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(request).await.is_err() {
        return false;
    }
    let mut buffer = [0u8; 128];
    let Ok(read) = stream.read(&mut buffer).await else {
        return false;
    };
    String::from_utf8_lossy(&buffer[..read]).starts_with("HTTP/1.1 200")
}

/// 启动侧车后端并等待健康检查通过。
async fn start_backend(app: &tauri::AppHandle) -> Result<u16, String> {
    let port = find_free_port().ok_or("无法找到空闲端口")?;
    let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
    let exe = resource_dir.join("tender-backend.exe");
    if !exe.exists() {
        return Err(format!("未找到侧车程序：{}", exe.display()));
    }

    let child = StdCommand::new(&exe)
        .arg("--port")
        .arg(port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("侧车启动失败：{error}"))?;

    {
        let state = app.state::<Mutex<BackendState>>();
        let mut guard = state.lock().map_err(|_| "后端状态锁异常".to_string())?;
        guard.port = Some(port);
        guard.child = Some(child);
    }

    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        if health_ok(port).await {
            println!("[tender-backend] 已在 http://127.0.0.1:{port} 就绪");
            return Ok(port);
        }
        tokio::time::sleep(Duration::from_millis(400)).await;
    }
    Err(format!(
        "后端启动超时：http://127.0.0.1:{port}/health 60 秒内未通过健康检查"
    ))
}

fn kill_backend(app: &tauri::AppHandle) {
    let state = app.state::<Mutex<BackendState>>();
    let mut guard = match state.lock() {
        Ok(guard) => guard,
        Err(_) => return,
    };
    if let Some(mut child) = guard.child.take() {
        let _ = child.kill();
        let _ = child.wait();
        println!("[tender-backend] 已停止");
    }
}

/// 前端在启动时调用：返回侧车后端地址；未启动则拉起并等待健康检查。
#[tauri::command]
async fn get_backend_url(app: tauri::AppHandle) -> Option<String> {
    // 开发模式（tauri dev）使用独立后端（默认 8000），只有正式安装包才拉起侧车。
    if cfg!(debug_assertions) {
        return None;
    }
    let state = app.state::<Mutex<BackendState>>();
    if let Some(port) = state.lock().ok()?.port {
        return Some(format!("http://127.0.0.1:{port}"));
    }
    match start_backend(&app).await {
        Ok(port) => Some(format!("http://127.0.0.1:{port}")),
        Err(error) => {
            eprintln!("[tender-backend] {error}");
            None
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(Mutex::new(BackendState::default()))
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .build(tauri::generate_context!())
        .expect("启动投标分析桌面程序失败")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                kill_backend(app_handle);
            }
        });
}
