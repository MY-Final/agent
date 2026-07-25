# 投标分析 Agent 后端（第一阶段）

这是桌面端投标分析工具的基础后端。当前阶段只提供任务管理、文件关联、任务状态、基础设施健康检查，不包含 AI、文档解析、匹配或内容生成逻辑。

## 技术栈

- Python 3.11+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 async + asyncpg + PostgreSQL
- redis.asyncio
- aioboto3 + MinIO（S3 兼容）

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

必填配置包括 PostgreSQL、Redis 和 MinIO 连接信息。`MINIO_ENDPOINT` 只填写 `host:port`，协议由 `MINIO_SECURE` 控制。

## 启动

在 `backend` 目录运行：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时 lifespan 会执行以下操作：

1. 连接 PostgreSQL，并通过 `Base.metadata.create_all()` 创建 `tasks`、`task_files` 表。
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

## 当前边界

- 数据库初始化使用 `create_all`，适合第一阶段启动。进入持续迭代后建议引入 Alembic 管理 schema 迁移。
- Redis 当前用于连接与健康检查，为后续任务队列、进度和缓存预留。第一阶段 Redis 不可用不会阻止应用启动，`/health` 会返回 `redis: down`。
- 删除文件或任务时先删除 MinIO 对象，再提交数据库删除；对象存储失败时数据库记录会保留，便于重试和排查。
- 文件接口只接收标准 multipart 附件上传，不读取调用端或服务端的本地文件路径。
