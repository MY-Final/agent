# 投标分析 Agent

一个面向桌面端的投标分析工具，包含 FastAPI 后端和 Vue 3 + Tauri 2 桌面客户端。当前主流程已打通：

```text
创建任务 -> 上传 PDF/DOCX -> 启动 Agent -> 结构化解析
-> 人工确认 -> 公司资质匹配 -> 查看匹配结果
```

## 当前能力

- 任务管理、状态跟踪和 MinIO 文件存储
- PDF/DOCX 文本提取，扫描 PDF 支持 PaddleOCR
- OpenAI 兼容接口的结构化标书解析
- 可动态管理和切换多个 OpenAI 兼容 LLM 提供商
- 公司证书、业绩、人员证书和公司信息知识库
- 基于确定性规则的资质匹配
- LangGraph 单任务流程编排与人工确认中断
- Vue 3 + Element Plus 桌面工作台
- Web 与桌面端共用的多 LLM 提供商可视化设置页，支持模型发现和连接测试
- PostgreSQL 持久化、Redis 连接预留和统一中文错误提示

## 项目结构

```text
agent/
├── backend/              # FastAPI、Skills、LangGraph 和数据库模型
│   ├── app/
│   ├── requirements.txt
│   └── README.md
├── desktop/              # Vue 3、TypeScript、Vite 和 Tauri 2
│   ├── src/
│   ├── src-tauri/
│   └── README.md
└── AGENTS.md             # 仓库协作规范
```

## 环境要求

- Python 3.11+
- Node.js 20+
- Rust 1.88
- Windows WebView2 与 Microsoft C++ Build Tools
- PostgreSQL、Redis 和 MinIO
- 可用的 OpenAI 兼容模型接口

## 启动后端

首次运行时，在 PowerShell 中执行：

```powershell
cd D:\Repos\agent\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

按实际环境修改 `backend/.env` 后启动：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后可访问 Swagger <http://127.0.0.1:8000/docs> 和健康检查 <http://127.0.0.1:8000/health>。完整配置、接口和测试示例见 [backend/README.md](backend/README.md)。

## 启动桌面端

另开一个 PowerShell 窗口：

```powershell
cd D:\Repos\agent\desktop
npm install
npm run tauri dev
```

首次启动会编译 Rust 依赖，可能需要几分钟。只调试 Web 界面时运行 `npm run dev`，浏览器访问 <http://127.0.0.1:1420>。Tauri 开发窗口使用独立的 `1421` 端口，因此两者可以同时运行。

桌面端默认连接 `http://127.0.0.1:8000`。可点击左下角连接区域修改后端地址，并检测 PostgreSQL、Redis 和 MinIO 状态。
侧栏“系统设置”可管理多个 OpenAI 兼容 LLM 提供商，并查看当前实际生效的脱敏配置。

## 桌面端操作流程

1. 在任务列表点击“新建任务”。
2. 填写项目名称，选择 PDF 或 DOCX 标书并提交。
3. 进入任务详情后点击“启动分析”。
4. 在解析结果页核对项目信息、资格要求、评分办法和废标条款。
5. 当任务进入 `waiting_confirm` 时点击“确认并继续”。
6. 匹配完成后查看已满足、缺失和风险项目。

## 检查与构建

后端：

```powershell
cd D:\Repos\agent\backend
python -m compileall -q app
python -m pip check
```

桌面端：

```powershell
cd D:\Repos\agent\desktop
npm run type-check
npm run build
cargo check --manifest-path src-tauri/Cargo.toml -j 1
```

## Windows 安装包

桌面端已配置 NSIS `.exe` 和 WiX `.msi` 两种安装包。在 Windows PowerShell 中执行：

```powershell
cd D:\Repos\agent\desktop
npm install
npm run tauri:build
```

安装包生成在 `desktop/src-tauri/target/release/bundle/nsis/` 和 `desktop/src-tauri/target/release/bundle/msi/`。当前推荐只打包 GUI，FastAPI 及 PostgreSQL、Redis、MinIO 作为独立服务运行；完整环境要求、单格式构建命令、WebView2 注意事项以及未来 PyInstaller/Nuitka Sidecar 方案见 [desktop/README.md](desktop/README.md)。

## 配置安全

不要提交 `backend/.env`、LLM API Key、数据库密码或 MinIO 凭据。`.env.example` 仅保留占位值。标书原文、解析结果和公司资质数据均应按敏感业务数据处理。

## 当前边界

当前版本不包含多用户登录、多 Agent 协作、RAG/向量检索、自动报告生成、经分表生成和高并发任务队列。解析与匹配接口仍以同步调用为主。
