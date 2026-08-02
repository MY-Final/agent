# 基础设施独立部署指南

本文针对 `deploy/infra.docker-compose.yml`（MinIO / Redis / PostgreSQL / MySQL 独立编排），适合在服务器上单独部署基础设施，不启动业务后端。

> 如果只是部署整个业务系统（后端 + 数据库 + 对象存储一套），直接用仓库根目录的 `docker-compose.yml`，按 [README.md](README.md) 操作即可，基础设施会一起启动，不需要本文。

## 1. 前置条件

- Linux 服务器（示例为 Ubuntu/Debian，命令用 root 或 `sudo` 执行；Windows 服务器需把路径换成盘符）
- Docker Engine 20.10+ 且带 Compose 插件
- 服务器能访问 Docker Hub / Quay.io 拉取镜像

检查 Docker：

```bash
docker --version
docker compose version
```

## 2. 创建数据目录

```bash
mkdir -p /opt/dockerApp/minio/data /opt/dockerApp/minio/config
mkdir -p /opt/dockerApp/redis/data /opt/dockerApp/redis/conf /opt/dockerApp/redis/logs
mkdir -p /opt/dockerApp/postgresql/data /opt/dockerApp/postgresql/backup
mkdir -p /opt/dockerApp/mysql/data /opt/dockerApp/mysql_local/data
```

## 3. 准备 redis.conf（必需）

Redis 容器启动时会读取宿主机上的 `/opt/dockerApp/redis/conf/redis.conf`。**该文件必须先真实存在**，否则 Docker 会自动创建同名目录，Redis 会启动失败。

最小可用配置：

```conf
port 6379
appendonly yes
appendfilename "appendonly.aof"
```

> 注意：容器内部监听 6379，`redis.conf` 里的 `port` 要保持 6379，不要改成宿主机端口 16379（宿主机端口由 Compose 映射）。

## 4. 准备环境变量

```bash
cd /path/to/agent   # 仓库目录
cp deploy/infra.env.example deploy/infra.env
vi deploy/infra.env
```

至少修改以下口令（保持默认值 `change-me-please` 会有安全风险）：

- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`（MinIO 控制台登录）
- `POSTGRES_PASSWORD`（业务数据库）
- `MYSQL_ROOT_PASSWORD` / `MYSQL_LOCAL_ROOT_PASSWORD`（如用到 MySQL）

## 5. 拉取镜像并启动

```bash
docker compose --env-file deploy/infra.env -f deploy/infra.docker-compose.yml up -d
```

查看状态：

```bash
docker compose -f deploy/infra.docker-compose.yml ps
```

所有服务应显示 `healthy`（或 `Up`）。首次启动拉镜像需要一些时间。

## 6. 验证各服务

| 服务 | 验证命令 | 预期结果 |
| --- | --- | --- |
| PostgreSQL | `docker exec local-postgres pg_isready -U postgres` | `accepting connections` |
| Redis | `docker exec redis_localhost redis-cli ping` | `PONG` |
| MinIO | 浏览器打开 `http://<服务器IP>:29001`，用 `MINIO_ROOT_USER/PASSWORD` 登录 | 控制台正常打开 |
| MySQL | `docker exec mysql mysql -uroot -p` | 输入口令后进入 SQL 提示符 |

日志排查：

```bash
docker compose -f deploy/infra.docker-compose.yml logs -f <服务名>
```

## 7. 与业务后端联用

推荐直接用根目录 `docker-compose.yml` 全栈部署（一套网络，服务名互通）。若后端单独部署、想连本机这套基础设施，把后端的连接配置指到宿主机端口：

| 服务 | 连接方式 |
| --- | --- |
| PostgreSQL | `postgresql://postgres:<口令>@<服务器IP>:15432/<库名>` |
| Redis | `redis://<服务器IP>:16379/0` |
| MinIO | Endpoint `http://<服务器IP>:29000`，`MINIO_SECURE=false`，并手动创建存储桶 |

## 8. 备份与恢复

```bash
# PostgreSQL：逻辑备份
docker exec local-postgres pg_dump -U postgres postgres > backup.sql

# 恢复
cat backup.sql | docker exec -i local-postgres psql -U postgres
```

MinIO / Redis / MySQL 的数据都在 `/opt/dockerApp/` 下，直接备份对应目录即可（建议先停止服务再复制，保证一致性）：

```bash
docker compose -f deploy/infra.docker-compose.yml stop
tar -czf infra-backup-$(date +%F).tar.gz -C /opt dockerApp
docker compose -f deploy/infra.docker-compose.yml start
```

## 9. 安全建议

- 所有口令务必修改，并保存在 `deploy/infra.env`（该文件已在 .gitignore 中，不会提交）。
- 服务器防火墙只放行实际需要的端口：`29001`（MinIO 控制台，按需）、`29000`（S3 API）、`15432`（如需远程连库）、`16379`、`13306/33306`。
- 数据库端口不建议直接暴露公网；生产环境建议在前面加 HTTPS 反向代理。
- 定期备份 `/opt/dockerApp`，并验证备份可恢复。

## 10. 常见问题

**Redis 启动后立即退出**：`redis.conf` 被 Docker 当成了目录。删除该目录，放置真实配置文件后 `docker compose -f deploy/infra.docker-compose.yml up -d` 重启。

**MinIO 健康检查失败**：个别镜像版本未内置 `curl`，可将 healthcheck 改为 `["CMD", "mc", "ready", "local"]`。

**MySQL 健康检查报错**：口令含 `$` 等特殊字符时，检查 `.env` 中值是否被引号包裹导致转义问题。

**端口被占用**：`ss -tlnp | grep <端口>` 查看占用进程，或修改 compose 文件中的宿主机端口映射。
