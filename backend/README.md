# 投标分析 Agent 后端（第二阶段）

这是桌面端投标分析工具的后端。当前已提供任务和文件管理，以及独立的标书解析 Skill；本阶段不包含资质匹配、报告生成或 Agent 编排。

## 技术栈

- Python 3.11+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 async + asyncpg + PostgreSQL
- redis.asyncio
- aioboto3 + MinIO（S3 兼容）
- PyMuPDF + PaddleOCR + python-docx
- OpenAI 兼容结构化输出接口

## 项目结构

```text
backend/
├── app/
│   ├── main.py
│   ├── api/v1/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── skills/
│   └── utils/
├── .env.example
├── requirements.txt
└── README.md
```

## 准备环境

进入 `backend` 目录，创建并激活虚拟环境：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

复制环境配置并按实际基础设施地址修改：

```powershell
Copy-Item .env.example .env
```

必填配置包括 PostgreSQL、Redis、MinIO 和 LLM 连接信息。`MINIO_ENDPOINT` 只填写 `host:port`，协议由 `MINIO_SECURE` 控制。LLM 使用 OpenAI 兼容接口：

```dotenv
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://你的服务地址/v1
LLM_MODEL_NAME=模型名称
```

使用 OpenAI 官方接口时可将 `LLM_BASE_URL` 留空。未配置 `LLM_API_KEY` 不影响服务启动，但调用解析接口会返回明确的配置错误。

## 启动

在 `backend` 目录运行：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时 lifespan 会执行以下操作：

1. 连接 PostgreSQL，并通过 `Base.metadata.create_all()` 创建 `tasks`、`task_files`、`task_parse_results` 表。
2. 建立并检查 Redis 连接；Redis 不可用时以降级模式继续启动。
3. 检查 MinIO bucket，不存在时自动创建。
4. 关闭应用时释放 Redis、MinIO 和数据库资源。

接口文档：

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- 健康检查: `http://localhost:8000/health`

## API

所有业务响应采用统一格式：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

已实现接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 检查 PostgreSQL、Redis、MinIO |
| POST | `/api/v1/tasks` | 创建任务 |
| GET | `/api/v1/tasks` | 任务列表，支持 `status`、`page`、`page_size` |
| GET | `/api/v1/tasks/{task_id}` | 任务详情及文件列表 |
| PUT | `/api/v1/tasks/{task_id}` | 更新任务基础信息 |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务和 MinIO 关联对象 |
| PATCH | `/api/v1/tasks/{task_id}/status` | 更新任务状态 |
| POST | `/api/v1/tasks/{task_id}/files/upload` | multipart 文件上传 |
| GET | `/api/v1/tasks/{task_id}/files` | 文件列表 |
| GET | `/api/v1/tasks/{task_id}/files/{file_id}/download` | 获取预签名下载 URL |
| DELETE | `/api/v1/tasks/{task_id}/files/{file_id}` | 删除数据库记录和 MinIO 对象 |
| POST | `/api/v1/skills/parse` | 通过 task_id、file_id 或 object_key 独立调用解析 Skill |
| POST | `/api/v1/tasks/{task_id}/parse` | 解析任务下全部 PDF/DOCX 文件 |
| GET | `/api/v1/tasks/{task_id}/parse-result` | 获取任务最新解析结果 |

任务状态为：`created`、`parsing`、`analyzing`、`waiting_confirm`、`generating`、`completed`、`failed`。

## 调用示例

创建任务：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/tasks `
  -ContentType application/json `
  -Body '{"project_name":"示例项目","remark":"第一版","source":"desktop"}'
```

文件添加统一使用 multipart 上传接口，字段名为 `file`。桌面端选择附件后，应直接将文件内容发送到 `/files/upload`，不要传递本地文件路径。预签名下载接口可使用 `expires_in` 查询参数覆盖默认有效期，范围为 1 秒到 7 天。

## 测试标书解析

推荐主流程：创建任务，上传 PDF 或 DOCX，然后调用任务级解析接口。

```powershell
$taskId = "替换为任务ID"
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/parse"
```

独立 Skill 接口一次必须且只能提供 `task_id`、`file_id`、`object_key` 中的一个：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/skills/parse `
  -ContentType application/json `
  -Body '{"file_id":"替换为文件ID"}'
```

查询任务最近一次解析记录：

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/parse-result"
```

PDF 先由 PyMuPDF 提取文字；有效字符少于 `PDF_TEXT_MIN_CHARS` 时才懒加载 PaddleOCR。PaddleOCR 在第一次识别扫描件时需要初始化模型，耗时会明显高于后续请求。DOCX 会提取正文段落和表格单元格。临时文件在每次解析结束后自动清理。

解析成功后结果写入 `task_parse_results`，任务状态更新为 `waiting_confirm`。提取、MinIO 下载或大模型调用失败时会写入失败记录，并将关联任务状态更新为 `failed`。

## 当前边界

- 数据库初始化使用 `create_all`，适合当前开发阶段。进入持续迭代后建议引入 Alembic 管理 schema 迁移。
- Redis 当前用于连接与健康检查，为后续任务队列、进度和缓存预留。Redis 不可用不会阻止应用启动，`/health` 会返回 `redis: down`。
- 删除文件或任务时先删除 MinIO 对象，再提交数据库删除；对象存储失败时数据库记录会保留，便于重试和排查。
- 文件接口只接收标准 multipart 附件上传，不读取调用端或服务端的本地文件路径。
- 标书解析目前为同步请求，适合调试与验证；长文档和 OCR 后续可平滑迁移到异步任务队列。
- 当前只解析 PDF 和 DOCX，不包含资质匹配、报告生成或 Agent 工作流。
