# 投标分析 Agent 后端（第三阶段）

这是桌面端投标分析工具的后端。当前已提供任务和文件管理、标书解析 Skill、公司资质知识库、确定性资质匹配 Skill，以及基于 LangGraph 的单任务分析 Agent。当前 Agent 支持自动解析、人工确认中断、确认后匹配和持久化恢复。

## 技术栈

- Python 3.11+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 async + asyncpg + PostgreSQL
- redis.asyncio
- aioboto3 + MinIO（S3 兼容）
- PyMuPDF + PaddleOCR + python-docx
- OpenAI 兼容结构化输出接口
- PostgreSQL 结构化资质知识库与规则匹配
- LangGraph + PostgreSQL checkpoint

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

Windows 推荐在 `backend` 目录运行以下命令，启动入口会为 psycopg 配置兼容的事件循环：

```powershell
python -m app
```

开发时需要热重载可继续使用：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时 lifespan 会执行以下操作：

1. 连接 PostgreSQL，并通过 `Base.metadata.create_all()` 创建任务、解析结果、资质知识库、匹配结果和 Agent 运行表。
2. 建立并检查 Redis 连接；Redis 不可用时以降级模式继续启动。
3. 检查 MinIO bucket，不存在时自动创建。
4. 初始化 LangGraph PostgreSQL checkpoint 表和连接。
5. 关闭应用时释放 LangGraph、Redis、MinIO 和数据库资源。

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
| POST/GET | `/api/v1/qualifications/certificates` | 新增或查询企业资质证书 |
| GET/PUT/DELETE | `/api/v1/qualifications/certificates/{id}` | 资质证书详情、更新、删除 |
| POST/GET | `/api/v1/qualifications/performances` | 新增或查询业绩记录 |
| GET/PUT/DELETE | `/api/v1/qualifications/performances/{id}` | 业绩详情、更新、删除 |
| POST/GET | `/api/v1/qualifications/personnel` | 新增或查询人员证书 |
| GET/PUT/DELETE | `/api/v1/qualifications/personnel/{id}` | 人员证书详情、更新、删除 |
| POST/GET | `/api/v1/qualifications/company` | 新增或查询公司信息 |
| GET/PUT/DELETE | `/api/v1/qualifications/company/{id}` | 公司信息详情、更新、删除 |
| POST | `/api/v1/skills/match` | 通过 task_id 或 parse_result_id 独立匹配 |
| POST | `/api/v1/tasks/{task_id}/match` | 使用任务最新成功解析结果执行匹配 |
| GET | `/api/v1/tasks/{task_id}/match-result` | 获取任务最新匹配报告 |
| POST | `/api/v1/tasks/{task_id}/agent/start` | 启动 Agent，自动解析并停在人工确认节点 |
| GET | `/api/v1/tasks/{task_id}/agent/status` | 查询 Agent 当前步骤、摘要和错误信息 |
| POST | `/api/v1/tasks/{task_id}/agent/confirm` | 确认解析结果，继续执行资质匹配 |
| POST | `/api/v1/tasks/{task_id}/agent/cancel` | 取消正在等待确认的 Agent 流程 |

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

## 测试资质知识库

金额字段统一按“元”保存，币种默认使用 `CNY`。证书状态使用稳定枚举值：`valid`、`expired`、`revoked`。

新增企业资质证书：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/qualifications/certificates `
  -ContentType application/json `
  -Body '{"name":"建筑工程施工总承包","level":"一级","specialty":"建筑工程","cert_number":"CERT-001","valid_from":"2025-01-01","valid_to":"2028-12-31","status":"valid"}'
```

新增业绩：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/qualifications/performances `
  -ContentType application/json `
  -Body '{"project_name":"办公楼建设项目","project_amount":8000000,"currency":"CNY","start_date":"2025-01-01","end_date":"2025-12-31","is_completed":true,"related_qualification":"建筑工程","description":"建筑工程施工总承包项目"}'
```

新增人员证书：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/qualifications/personnel `
  -ContentType application/json `
  -Body '{"person_name":"张三","cert_type":"一级建造师","specialty":"建筑工程","cert_number":"PERSON-001","valid_to":"2028-12-31","is_on_job":true}'
```

新增公司信息：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/qualifications/company `
  -ContentType application/json `
  -Body '{"company_name":"示例建设有限公司","legal_person":"李四","registered_capital":20000000,"establish_date":"2015-01-01","extra_info":{}}'
```

列表接口支持分页，并提供名称、有效性、金额范围、完成状态、在职状态等查询参数。资质记录的 `file_object_key` 可保存已上传到 MinIO 的证明文件对象键；删除记录时会同步删除该对象。

## 测试资质匹配

推荐顺序：先完成标书解析，再录入公司资质数据，最后执行任务级匹配：

```powershell
$taskId = "替换为已经解析成功的任务ID"
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/match"
```

独立匹配接口一次必须且只能提供 `task_id` 或 `parse_result_id`：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/skills/match `
  -ContentType application/json `
  -Body '{"parse_result_id":"替换为解析结果ID"}'
```

查询任务最近一次匹配报告：

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/match-result"
```

匹配 Skill 逐条处理解析结果中的 `qualifications`，根据证书名称和等级、有效期、业绩关键词和金额、业绩数量和时间、人员证书和在职状态、注册资本等结构化规则输出 `matched_items`、`missing_items` 和 `risk_items`。规则无法可靠判断的要求会进入风险项并提示人工核验，不会调用大模型作主观判断。匹配报告写入 `task_match_results`，匹配时任务状态为 `analyzing`，成功后更新为 `waiting_confirm`，失败后更新为 `failed`。

## 测试 Agent 流程

Agent 主路径为：上传标书文件 -> 自动解析 -> 等待人工确认 -> 确认后匹配 -> 完成。启动前需要先为任务上传至少一个 PDF 或 DOCX 文件，并按需录入公司资质知识库。

启动 Agent。该请求同步执行解析，成功后返回 `current_step: wait_confirm`：

```powershell
$taskId = "替换为任务ID"
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/agent/start"
```

查询状态。浏览器刷新或服务重启后，可继续用同一个接口查询持久化状态：

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/agent/status"
```

确认解析结果并继续匹配。请求体可使用 `{}`，也可附带人工备注：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/agent/confirm" `
  -ContentType application/json `
  -Body '{"remark":"解析内容已核对，可以继续匹配"}'
```

确认请求同步执行匹配。成功后 Agent 的 `current_step` 和 `status` 均为 `completed`，任务状态也会更新为 `completed`。解析结果保存在 `task_parse_results`，匹配结果保存在 `task_match_results`，业务运行状态保存在 `agent_runs`，节点 checkpoint 由 LangGraph 保存到 PostgreSQL。

等待确认时可取消当前流程：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/tasks/$taskId/agent/cancel"
```

取消不会删除已经生成的解析结果。第一版只允许取消等待确认的流程，不提供解析或匹配执行中的强制终止。

## 当前边界

- 数据库初始化使用 `create_all`，适合当前开发阶段。进入持续迭代后建议引入 Alembic 管理 schema 迁移。
- Redis 当前用于连接与健康检查，为后续任务队列、进度和缓存预留。Redis 不可用不会阻止应用启动，`/health` 会返回 `redis: down`。
- 删除文件或任务时先删除 MinIO 对象，再提交数据库删除；对象存储失败时数据库记录会保留，便于重试和排查。
- 文件接口只接收标准 multipart 附件上传，不读取调用端或服务端的本地文件路径。
- 标书解析目前为同步请求，适合调试与验证；长文档和 OCR 后续可平滑迁移到异步任务队列。
- 资质匹配只使用结构化精确规则，不使用 RAG、向量库或大模型判断；规则无法覆盖的复杂条款需要人工核验。
- 当前只解析 PDF 和 DOCX。
- Agent 当前是单任务固定流程，不包含多 Agent、ReAct、RAG、报告生成、经分表生成或高并发任务队列。
- 解析和匹配节点目前随接口同步执行；人工确认节点使用 LangGraph `interrupt`，checkpoint 和业务状态均持久化到 PostgreSQL。
