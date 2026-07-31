import logging
from urllib.parse import urlsplit

import aioboto3
import asyncpg
import redis.asyncio as aioredis
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.runtime_config import (
    RUNTIME_CONFIG_FILE,
    build_database_url,
    build_redis_url,
    load_runtime_config,
    save_runtime_config,
)
from app.schemas.runtime import (
    ComponentHealth,
    MinioConfig,
    PostgresConfig,
    RedisConfig,
    RuntimeSettingsInput,
    RuntimeSettingsRead,
    RuntimeTestResult,
)


logger = logging.getLogger(__name__)

_MASK = "********"


class RuntimeSettingsService:
    @staticmethod
    async def get_read() -> RuntimeSettingsRead:
        runtime = load_runtime_config()
        postgres = _postgres_from_runtime(runtime)
        redis = _redis_from_runtime(runtime)
        minio = _minio_from_runtime(runtime)
        health = RuntimeTestResult(
            postgres=await _test_postgres(postgres),
            redis=await _test_redis(redis),
            minio=await _test_minio(minio),
        )
        return RuntimeSettingsRead(
            postgres=_mask_postgres(postgres),
            redis=_mask_redis(redis),
            minio=_mask_minio(minio),
            health=health,
            config_file=str(RUNTIME_CONFIG_FILE),
        )

    @staticmethod
    async def test(payload: RuntimeSettingsInput) -> RuntimeTestResult:
        return RuntimeTestResult(
            postgres=await _test_postgres(payload.postgres),
            redis=await _test_redis(payload.redis),
            minio=await _test_minio(payload.minio),
        )

    @staticmethod
    async def save(payload: RuntimeSettingsInput) -> RuntimeSettingsRead:
        save_runtime_config(
            {
                "postgres": payload.postgres.model_dump(),
                "redis": payload.redis.model_dump(),
                "minio": payload.minio.model_dump(),
            }
        )
        logger.info("已保存运行时基础设施配置：%s", RUNTIME_CONFIG_FILE)
        return await RuntimeSettingsService.get_read()


def _postgres_from_runtime(runtime: dict) -> PostgresConfig:
    raw = runtime.get("postgres") or {}
    if raw.get("host"):
        return PostgresConfig(**raw)
    url = make_url(settings.database_url)
    return PostgresConfig(
        host=url.host or "127.0.0.1",
        port=url.port or 5432,
        user=url.username or "postgres",
        password=url.password,
        database=url.database or "tender",
    )


def _redis_from_runtime(runtime: dict) -> RedisConfig:
    raw = runtime.get("redis") or {}
    if raw.get("host"):
        return RedisConfig(**raw)
    parts = urlsplit(settings.redis_url)
    db = 0
    if parts.path and parts.path != "/":
        try:
            db = int(parts.path.lstrip("/"))
        except ValueError:
            db = 0
    return RedisConfig(
        host=parts.hostname or "127.0.0.1",
        port=parts.port or 6379,
        password=parts.password,
        db=db,
    )


def _minio_from_runtime(runtime: dict) -> MinioConfig:
    raw = runtime.get("minio") or {}
    if raw.get("endpoint"):
        return MinioConfig(**raw)
    return MinioConfig(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )


def _mask_postgres(config: PostgresConfig) -> PostgresConfig:
    return config.model_copy(update={"password": _MASK if config.password else None})


def _mask_redis(config: RedisConfig) -> RedisConfig:
    return config.model_copy(update={"password": _MASK if config.password else None})


def _mask_minio(config: MinioConfig) -> MinioConfig:
    return config.model_copy(update={"secret_key": _MASK if config.secret_key else None})


async def _test_postgres(config: PostgresConfig) -> ComponentHealth:
    try:
        connection = await asyncpg.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password or None,
            database=config.database,
            timeout=5,
        )
        try:
            await connection.execute("SELECT 1")
        finally:
            await connection.close()
        return ComponentHealth(
            ok=True,
            message=f"连接成功（{config.host}:{config.port}/{config.database}）",
        )
    except Exception as exc:
        return ComponentHealth(ok=False, message=f"连接失败：{_short_error(exc)}")


async def _test_redis(config: RedisConfig) -> ComponentHealth:
    url = build_redis_url(config.model_dump())
    client = aioredis.from_url(
        url,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
        await client.ping()
        return ComponentHealth(
            ok=True,
            message=f"连接成功（{config.host}:{config.port}/{config.db}）",
        )
    except Exception as exc:
        return ComponentHealth(ok=False, message=f"连接失败：{_short_error(exc)}")
    finally:
        await client.aclose()


async def _test_minio(config: MinioConfig) -> ComponentHealth:
    scheme = "https" if config.secure else "http"
    session = aioboto3.Session()
    try:
        async with session.client(
            "s3",
            endpoint_url=f"{scheme}://{config.endpoint}",
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key or "",
            region_name=settings.minio_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        ) as client:
            try:
                await client.head_bucket(Bucket=config.bucket)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"404", "NoSuchBucket", "NotFound"}:
                    return ComponentHealth(
                        ok=True,
                        message=(
                            f"连接成功（{config.endpoint}），桶 {config.bucket} "
                            "不存在，启动时会自动创建"
                        ),
                    )
                raise
        return ComponentHealth(
            ok=True,
            message=f"连接成功（{config.endpoint}，桶 {config.bucket}）",
        )
    except Exception as exc:
        return ComponentHealth(ok=False, message=f"连接失败：{_short_error(exc)}")


def _short_error(exc: Exception) -> str:
    message = str(exc).strip().replace("\n", " ")
    return message[:160] or exc.__class__.__name__
