# 服务器部署指南（Docker Compose）

把后端 + PostgreSQL + Redis + MinIO 编排成一套服务，桌面端通过"设置 → 后端地址"远程连接。

## 服务组成

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| backend | 8000 | FastAPI 应用（自动建表/迁移，启动依赖下方三者健康） |
| postgres | 5432（内网） | 业务数据 + LangGraph 检查点 |
| redis | 6379（内网） | 缓存/会话 |
| minio | 9000（S3 API）/ 9001（控制台） | 标书文件对象存储 |
| web | 8080 | Web 前端（nginx 托管，/api 反代到 backend） |

## 快速开始

```bash
# 1. 准备环境变量
cp deploy/.env.example .env
vi .env   # 至少修改 POSTGRES_PASSWORD / MINIO 口令，并填写 LLM_API_KEY

# 2. 构建并启动
docker compose up -d --build

# 3. 验证
curl http://127.0.0.1:8000/health
docker compose ps
```

桌面端连接：设置 → 后端地址填 `http://<服务器IP>:8000`，健康检查通过即可使用。

Web 前端：浏览器访问 `http://<服务器IP>:8080`。前端由 nginx 容器托管，`/api` 与 `/health` 自动反代到 backend（含 SSE 流式接口），上传上限 600MB，一般无需额外配置；需要指向其他后端地址时，在构建前设置 `VITE_BACKEND_URL`。

Web 与桌面端均需登录：默认账号 `admin / admin`，首次登录会强制要求修改密码（修改后的密码持久化在 `auth_data` 卷中，重启不丢失）。

## 环境变量说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | tender / change-me-please / tender | PostgreSQL 口令务必修改 |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | minioadmin | MinIO 口令务必修改 |
| `MINIO_BUCKET` | tender-files | 标书文件桶，首次启动自动创建 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` | 空 / 空 / gpt-4.1-mini | 未在数据库配置默认提供商时的回退配置 |
| `WITH_OCR` | false | true 时镜像安装 PaddleOCR（CPU 版，体积 +2GB） |
| `CORS_ORIGINS` | ["*"] | JSON 数组或逗号分隔列表，桌面端直连一般保持 ["*"] |
| `VITE_BACKEND_URL` | 空 | Web 前端构建时指定的后端地址；留空表示同源反代 |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | admin / admin | 登录账号密码，默认账号首次登录强制改密 |
| `AUTH_SECRET` | 空 | JWT 签名密钥，留空由 AUTH_PASSWORD 派生；生产建议配置 |
| `AUTH_TOKEN_TTL_HOURS` | 24 | 登录 Token 有效期（小时） |
| `LOG_LEVEL` / `PDF_TEXT_MIN_CHARS` / `OCR_LANGUAGE` / `OCR_RENDER_SCALE` | INFO / 300 / ch / 2.0 | 日志与扫描件 OCR 调参 |

大模型提供商也可以在应用内配置：设置 → 大模型提供商，配置会存入数据库并优先生效。

## 扫描件 OCR

镜像默认**不含 OCR**（保持体积小），此时扫描版 PDF 会走文本层提取，提取不到有效文字时按失败处理。
需要 OCR 时重新构建：

```bash
WITH_OCR=true docker compose up -d --build backend
```

## 仅部署基础设施（可选）

如果只想单独跑 PostgreSQL / Redis / MinIO（不启动 backend），或者还需要 MySQL，使用独立的 `infra.docker-compose.yml`，与本仓库根目录的全栈编排互不冲突：

```bash
cp deploy/infra.env.example deploy/infra.env
vi deploy/infra.env   # 至少修改各服务的口令
docker compose --env-file deploy/infra.env -f deploy/infra.docker-compose.yml up -d
```

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| minio | 29000（S3 API）/ 29001（控制台） | 对象存储，数据在 `/opt/dockerApp/minio` |
| redis | 16379 | 缓存，需先在 `/opt/dockerApp/redis/conf/` 放好 `redis.conf` |
| postgres | 15432 | 业务数据库，数据在 `/opt/dockerApp/postgresql` |
| mysql / mysql_local | 13306 / 33306 | 其他项目使用，本项目不需要可删除 |

该文件用宿主机目录持久化数据，方便直接备份。注意 `redis.conf` 必须先存在于宿主机，否则 Docker 会把它当成目录，导致 Redis 启动失败。

完整的分步部署、验证、备份与排障说明见 [基础设施独立部署指南](infra-deployment.md)。

## 日常运维

```bash
docker compose logs -f backend        # 查看后端日志
docker compose restart backend        # 重启后端
docker compose down                   # 停止（数据保留在卷中）
docker compose down -v                # 停止并删除数据卷（不可恢复，谨慎）
```

数据全部保存在命名卷 `postgres_data` / `redis_data` / `minio_data`，升级时先备份：

```bash
docker compose exec postgres pg_dump -U tender tender > backup.sql
```

## 安全建议

- 服务器防火墙只放行 `8000`、`8080`（Web 前端，以及 `9001` 管理台按需放行），`5432/6379` 不对外。
- 建议在 `8000` 前加反向代理并启用 HTTPS（示例 Caddy）：

  ```
  api.example.com {
      reverse_proxy backend:8000
  }
  ```

  若通过域名访问，将 `CORS_ORIGINS` 设为你的桌面端来源，并把 `MINIO_ENDPOINT` 改为可达地址。
