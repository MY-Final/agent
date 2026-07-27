# 投标分析桌面端

基于 Vue 3、TypeScript、Element Plus 和 Tauri 2 的桌面工作台。当前支持：

```text
新建任务 -> 上传 PDF/DOCX -> 启动 Agent -> 查看解析结果
-> 人工确认 -> 查看资质匹配结果
```

## 已实现功能

- 任务列表、状态筛选、刷新和删除
- 新建任务并拖拽或选择 PDF/DOCX 标书
- 任务详情、附件补充上传和预签名下载
- 启动 Agent、五秒轮询运行状态和手动刷新
- 结构化展示解析结果与资质匹配结果
- `waiting_confirm` 状态下的人工确认入口
- 可配置后端地址及 PostgreSQL、Redis、MinIO 健康检查
- 系统设置页可新增、编辑、启停、删除和切换默认 LLM 提供商
- 可从 OpenAI 兼容服务获取模型列表、选择默认模型并测试实际连接
- 中文错误提示、加载状态和空状态

## 环境要求

- Node.js 20+
- Rust 1.88（由 `rust-toolchain.toml` 固定）
- Windows WebView2
- Microsoft C++ Build Tools
- 已启动的投标分析 FastAPI 后端

## 本地启动

先在一个 PowerShell 窗口启动后端：

```powershell
cd D:\Repos\agent\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

再在另一个 PowerShell 窗口启动桌面端：

```powershell
cd D:\Repos\agent\desktop
npm install
npm run tauri dev
```

首次启动需要编译 Rust 和 Tauri 依赖，可能等待几分钟；后续启动会明显更快。

只调试 Web 界面时运行，默认使用 `http://127.0.0.1:1420`：

```powershell
npm run dev
```

运行 Tauri 桌面端时会自动启动独立的 Vite 服务，使用
`http://127.0.0.1:1421`。因此网页版和桌面端可以同时运行：

```powershell
# PowerShell 窗口 1：网页版，端口 1420
npm run dev

# PowerShell 窗口 2：Tauri，内部使用端口 1421
npm run tauri dev
```

然后访问 <http://127.0.0.1:1420>。

## 后端地址

默认使用 `http://127.0.0.1:8000`。点击左下角连接区域可修改地址，并检测 PostgreSQL、Redis 和 MinIO 状态。配置保存在当前机器的本地存储中。

Agent 的启动和确认接口为同步长请求，桌面端设置了 10 分钟超时。解析或匹配结果尚未生成时，页面会显示正常空状态，不会把 404 当作流程故障。

## 测试主流程

1. 新建任务并填写项目名称。
2. 拖入或选择一个 PDF/DOCX 文件。
3. 创建成功后进入任务详情，确认文件列表正常。
4. 点击“启动分析”，等待任务进入“待确认”。
5. 检查解析结果后点击“确认并继续”。
6. 等待任务完成，检查匹配总结、已满足、缺失和风险项。
7. 左下角打开连接设置，确认 API、PostgreSQL、Redis、MinIO 均为正常。
8. 进入“系统设置”，填写提供商地址与密钥，获取模型列表并选择默认模型。
9. 点击“测试连接”，确认模型可调用后保存并按需设为默认提供商。

## 检查与构建

```powershell
npm run type-check
npm run build
cargo check --manifest-path src-tauri/Cargo.toml -j 1
npm run tauri build -- --debug
```

构建产物位于 `src-tauri/target/`，该目录不会提交到 Git。
