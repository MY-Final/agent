# 投标分析 Agent

一个面向桌面端的投标分析工具，包含 FastAPI 后端和 Vue 3 + Tauri 2 桌面客户端。当前主流程已打通：

```text
创建任务 -> 上传 PDF/DOCX -> 启动 Agent -> 结构化解析
-> 人工确认 -> 公司资质匹配 -> 查看匹配结果
```

## 当前能力

**任务与流程**

- 任务列表支持状态筛选与关键词搜索，首页工作台一屏汇总待确认、执行中、已完成、失败任务和证书预警
- LangGraph 单任务流程编排：解析 → 人工确认 → 资质匹配，支持人工确认中断、取消与驳回重解析

**标书解析**

- PDF/DOCX 文本提取，扫描 PDF 支持 PaddleOCR；OpenAI 兼容接口的结构化解析
- 模板驱动解析：字段即数据，前端按模板通用渲染，加字段不再改代码
- 可视化模板编辑器，可按公司/标书类型维护多套模板
- AI 自然语言生成模板：描述提取重点 → 生成建议 → 人工确认后保存
- 多版本溯源：每次解析独立成版本，支持并排对比与差异高亮
- 人工核对闭环：标书原文对照（文本搜索高亮 + PDF 页面预览）、字段就地修正、驳回后重新解析

**资质知识库与匹配**

- 公司信息、资质证书、业绩、人员证书四类数据管理界面，支持搜索筛选和 Excel 批量导入
- 证书临期（90 天）/过期/撤销/离职预警
- 基于确定性规则的资质匹配：证书等级、有效期、业绩金额、人员数量等逐项核验
- 匹配报告导出为 Excel（xlsx），含材料准备清单

**AI 与成本**

- 可动态管理和切换多个 OpenAI 兼容 LLM 提供商，支持模型发现和连接测试
- 所有 AI 调用自动记录用量：token、耗时、预估成本、成功/失败
- 统计与成本页：调用趋势、按用途/模型/任务分布、任务成功率与平均耗时

**技术底座**

- FastAPI + SQLAlchemy + PostgreSQL 持久化，Redis 连接预留，MinIO 文件存储
- Vue 3 + Element Plus + Tauri 2 桌面工作台，Web 与桌面端共用一套前端
- 统一中文错误提示与响应结构

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

1. 在“工作台”查看待办，或到任务列表点击“新建任务”。
2. 填写项目名称，选择解析模板（可选，默认模板），上传 PDF 或 DOCX 标书并提交。
3. 进入任务详情后点击“启动分析”。
4. 在解析结果页核对结构化结果：可切换/对比历史版本、打开原文对照（文本或 PDF 页面）、就地修正字段。
5. 审核不通过时点击“驳回并重新解析”（可改选模板），原结果保留为已驳回版本。
6. 当任务进入 `waiting_confirm` 时点击“确认并继续”。
7. 匹配完成后查看已满足、缺失和风险项目，可导出 Excel 报告（含材料准备清单）。
8. 在“资质知识库”维护公司证书、业绩、人员证书和公司信息，支持 Excel 导入与临期预警。
9. 在“统计与成本”查看全部 AI 调用的 token、耗时与预估成本。

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

当前版本不包含多用户登录与权限审计、桌面通知提醒、LLM 投标决策摘要、多任务横向机会对比、RAG/向量检索和高并发任务队列。解析与匹配接口仍以同步调用为主。
