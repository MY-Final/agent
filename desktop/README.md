# 投标分析桌面端

基于 Vue 3、TypeScript、Element Plus 和 Tauri 2 的投标分析工作台。当前主流程为：

```text
新建任务 -> 上传 PDF/DOCX -> 启动 Agent -> 查看解析结果
-> 人工确认 -> 查看公司资质匹配结果
```

## 已实现功能

- 任务列表、创建、详情、状态跟踪和附件管理
- 工作台首页：待办任务、证书预警与最近任务汇总
- 模板驱动标书解析：可视化模板编辑、AI 生成模板、多版本对比
- 人工核对闭环：原文对照（文本/PDF 页面）、字段就地修正、驳回重解析
- 资质知识库管理：公司/证书/业绩/人员四类数据 CRUD、Excel 导入、临期预警
- 资质匹配报告与 Excel 导出（含材料准备清单）
- 统计与成本：全部 AI 调用自动记录 token、耗时与预估成本
- 后端地址配置及 PostgreSQL、Redis、MinIO 健康检查
- 多 LLM 提供商管理、模型获取、默认模型选择和连接测试
- Web 调试端与 Tauri 开发端使用独立端口

## Windows 环境要求

- Node.js 20+ 和 npm
- Rust 1.88；项目通过 `rust-toolchain.toml` 固定工具链
- Visual Studio Build Tools，安装“使用 C++ 的桌面开发”工作负载
- Microsoft Edge WebView2 Runtime
- 可访问 npm、crates.io，以及首次打包所需的 Tauri 构建工具下载地址
- 已配置并启动的 FastAPI、PostgreSQL、Redis 和 MinIO 服务

可先执行 `npm run tauri -- info` 检查 Node、Rust、MSVC 和 WebView2 环境。

## 开发启动

先在一个 PowerShell 窗口启动后端：

```powershell
cd D:\Repos\agent\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

再启动桌面端：

```powershell
cd D:\Repos\agent\desktop
npm install
npm run tauri:dev
```

首次启动会编译 Rust 依赖，等待时间通常比后续启动长。仅调试 Web 页面时执行 `npm run dev`，访问 <http://127.0.0.1:1420>。Tauri 开发模式内部使用 `1421` 端口，因此 Web 和桌面窗口可以同时运行。

## 正式打包

在 Windows PowerShell 中执行：

```powershell
cd D:\Repos\agent\desktop
npm install
npm run type-check
npm run tauri:build
```

`tauri:build` 会先执行前端生产构建，再编译 Rust release 程序，最后同时生成 NSIS 和 MSI 安装包。也可只构建一种格式：

```powershell
npm run tauri:build:nsis
npm run tauri:build:msi
```

Windows 产物目录：

```text
src-tauri/target/release/tender-analysis-desktop.exe  # 主程序
src-tauri/target/release/bundle/nsis/                 # NSIS 安装程序 .exe
src-tauri/target/release/bundle/msi/                  # WiX 安装程序 .msi
```

当前版本实际产物（已验证可构建）：

```text
src-tauri/target/release/bundle/nsis/投标分析工作台_0.1.0_x64-setup.exe   # NSIS（推荐分发）
src-tauri/target/release/bundle/msi/投标分析工作台_0.1.0_x64_zh-CN.msi    # MSI（企业分发）
```

首次打包会下载并编译全部 Rust 依赖，耗时几分钟；之后增量构建明显加快。产物文件名随 `productName` 和 `version` 变化。

当前优先推荐分发 NSIS `.exe`，其安装范围为当前用户，不要求管理员权限；MSI 适合企业软件分发。安装程序采用 WebView2 在线引导模式，目标机器没有 WebView2 时需要联网下载。当前未配置代码签名，外部分发时 Windows SmartScreen 可能显示未知发布者提示。

若 Rust 编译出现 Windows 错误 `1455` 或“页面文件太小”，请关闭占用内存较高的程序、增大系统虚拟内存后重试；也可在当前 PowerShell 中先执行 `$env:CARGO_BUILD_JOBS='1'`，降低并行编译的内存占用。

## 应用配置

- 应用名称、版本、标识符、窗口和安装包配置：`src-tauri/tauri.conf.json`
- Rust 包版本：`src-tauri/Cargo.toml`
- npm 包版本：`package.json`
- 应用图标：`src-tauri/icons/`，可运行 `npm run tauri icon <源图片>` 重新生成
- 默认后端地址：`src/utils/settings.ts` 中的 `DEFAULT_BACKEND_URL`

发布新版本时同步更新以上三个版本字段。`bundle.windows.wix.upgradeCode` 必须永久保持不变，否则 Windows 会把升级包识别为另一个应用。

运行后也可点击左下角连接区域修改后端地址，配置保存在当前机器的本地存储中。默认地址为 `http://127.0.0.1:8000`。

系统设置页的“基础设施配置”可填写 PostgreSQL、Redis、MinIO 的连接信息（含密码与连接测试），保存后写入后端目录的 `runtime.env.json`，重启后端后生效；该文件已加入 `.gitignore`，不会被提交。

## 后端分发方案

### 方案 A：后端独立运行（当前推荐）

Tauri 安装包只包含桌面 GUI。部署方先启动 FastAPI 及 PostgreSQL、Redis、MinIO，用户再在桌面程序中填写后端地址。单机部署可继续使用 `http://127.0.0.1:8000`；局域网部署则填写服务器地址。此方案构建简单、日志和服务升级独立，适合当前阶段。

### 方案 B：后端作为 Sidecar（后续升级）

可使用 PyInstaller 或 Nuitka 将 FastAPI 后端打成 Windows 可执行文件，再通过 Tauri `externalBin` 打入安装包。具体步骤：

1. 用 PyInstaller 把后端打成单文件可执行程序（在 Windows 上执行）：

   ```powershell
   cd D:\Repos\agent\backend
   pip install pyinstaller
   pyinstaller --onefile --name tender-backend --collect-all paddleocr app/main.py
   ```

   将 `dist/tender-backend.exe` 放到 `desktop/src-tauri/binaries/`（目录名由 Tauri 侧车命名规则决定）。
2. 在 `tauri.conf.json` 的 `bundle` 中加入侧车：

   ```json
   {
     "bundle": {
       "externalBin": ["binaries/tender-backend"]
     }
   }
   ```
3. Rust 侧使用 `tauri-plugin-shell` 的 sidecar API 启动后端：
   - 启动时先探测一个空闲端口（如从 8000 起尝试），写入环境变量或启动参数，再 `Command::new_sidecar("tender-backend")` 拉起；
   - 轮询 `http://127.0.0.1:<port>/health`，健康通过后再让前端进入业务页；
   - 应用退出时终止子进程（`on_window_event` / 退出钩子），避免留下孤儿进程。
4. 需在 `capabilities/default.json` 增加 `shell:allow-execute`（或更窄的 sidecar 权限），并把默认后端地址改为动态端口。

实施时还需处理：端口冲突、异常退出、日志目录、临时文件、杀毒软件误报、子进程权限和约定关闭；并决定 PostgreSQL、Redis、MinIO 是继续作为外部服务，还是替换为适合单机嵌入的存储。OCR 和 Python 运行时会明显增加安装包体积。本阶段不自动集成后端。

## 发布前检查

```powershell
npm run type-check
npm run build
cargo check --manifest-path src-tauri/Cargo.toml -j 1
npm run tauri:build
```

安装后至少验证：后端连接、任务创建、附件上传、Agent 启动、人工确认、匹配结果和 LLM 设置页。构建目录 `src-tauri/target/` 已被 Git 忽略。
