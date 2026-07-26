import logging
import time
from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionFactory, close_database, init_database
from app.core.exceptions import AppException
from app.core.minio import minio_storage
from app.core.redis import redis_manager
from app.core.response import ApiResponse, success_response
from app.schemas.task import HealthData
from app.utils.validation import translate_validation_errors


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("正在启动 %s，运行环境：%s", settings.app_name, settings.app_env)
    try:
        await init_database()
        try:
            await redis_manager.connect()
        except Exception as exc:
            logger.warning(
                "Redis 暂时不可用，应用将以降级模式启动：%s",
                exc,
            )
        await minio_storage.connect()
        logger.info("PostgreSQL、Redis、MinIO 基础设施初始化完成")
        yield
    finally:
        await redis_manager.disconnect()
        await minio_storage.disconnect()
        await close_database()
        logger.info("应用已停止")


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "%s %s completed in %.2f ms",
            request.method,
            request.url.path,
            duration_ms,
        )
    return response


@app.exception_handler(AppException)
async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "msg": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 42200,
            "msg": "请求参数校验失败",
            "data": jsonable_encoder(translate_validation_errors(exc.errors())),
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    http_messages = {
        400: "请求参数错误",
        404: "请求的接口不存在",
        405: "请求方法不被允许",
        413: "上传内容过大",
        415: "不支持的媒体类型",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code * 100,
            "msg": http_messages.get(exc.status_code, "请求处理失败"),
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("处理请求时发生未捕获异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 50000, "msg": "服务器内部错误", "data": None},
    )


@app.get("/health", response_model=ApiResponse[HealthData], summary="健康检查")
async def health_check() -> ApiResponse[HealthData]:
    checks: dict[str, str] = {}

    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "up"
    except Exception:
        logger.exception("PostgreSQL 健康检查失败")
        checks["postgres"] = "down"

    try:
        checks["redis"] = "up" if await redis_manager.ping() else "down"
    except Exception:
        logger.exception("Redis 健康检查失败")
        checks["redis"] = "down"

    try:
        checks["minio"] = "up" if await minio_storage.ping() else "down"
    except Exception:
        logger.exception("MinIO 健康检查失败")
        checks["minio"] = "down"

    healthy = all(value == "up" for value in checks.values())
    result = HealthData(
        status="healthy" if healthy else "unhealthy",
        postgres=checks["postgres"],
        redis=checks["redis"],
        minio=checks["minio"],
    )
    return success_response(result, msg="服务正常" if healthy else "部分服务异常")
