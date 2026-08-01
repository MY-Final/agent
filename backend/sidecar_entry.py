"""PyInstaller 侧车入口：打包后的后端可执行程序从这里启动。

桌面端（Tauri）以子进程方式拉起本程序，传入 --port；
打包模式下基础设施配置来自系统设置保存的 runtime.env.json，
因此这里在导入应用前先把配置写进环境变量。
"""

import argparse
import asyncio
import os
import sys


def _apply_runtime_env() -> None:
    from app.core.runtime_config import (
        build_database_url,
        build_redis_url,
        load_runtime_config,
    )

    runtime = load_runtime_config()
    postgres = runtime.get("postgres") or {}
    redis = runtime.get("redis") or {}
    minio = runtime.get("minio") or {}

    if postgres.get("host") and postgres.get("database"):
        os.environ["DATABASE_URL"] = build_database_url(postgres)
    if redis.get("host"):
        os.environ["REDIS_URL"] = build_redis_url(redis)
    if minio.get("endpoint"):
        os.environ["MINIO_ENDPOINT"] = str(minio["endpoint"])
        os.environ["MINIO_ACCESS_KEY"] = str(minio.get("access_key") or "")
        os.environ["MINIO_SECRET_KEY"] = str(minio.get("secret_key") or "")
        os.environ["MINIO_BUCKET"] = str(minio.get("bucket") or "tender-files")
        os.environ["MINIO_SECURE"] = "true" if minio.get("secure") else "false"


def main() -> None:
    parser = argparse.ArgumentParser(description="投标分析 Agent 后端侧车")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
    )
    args = parser.parse_args()

    # 打包模式下必须先注入环境变量，否则 Settings() 会因为缺少必填项而失败。
    if getattr(sys, "frozen", False):
        _apply_runtime_env()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 显式导入应用，确保 PyInstaller 收集完整模块；随后交给 uvicorn 启动。
    import app.main  # noqa: F401
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
