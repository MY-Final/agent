import uuid
from contextlib import suppress
from dataclasses import dataclass
from time import perf_counter
from typing import NoReturn

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.schemas.llm_provider import (
    LLMConnectionBase,
    LLMConnectionTestRequest,
    LLMConnectionTestRead,
    LLMModelListRead,
)
from app.services.llm_provider_service import LLMProviderService
from app.utils.secrets import looks_like_masked_api_key


@dataclass(slots=True, frozen=True)
class LLMConnectionConfig:
    provider_id: uuid.UUID | None
    base_url: str
    api_key: str
    timeout_seconds: int


class LLMConnectionService:
    """通过后端检查 OpenAI 兼容服务，避免前端跨域和密钥暴露。"""

    @staticmethod
    async def list_models(
        session: AsyncSession,
        payload: LLMConnectionBase,
    ) -> LLMModelListRead:
        config = await LLMConnectionService._resolve_config(session, payload)
        client = LLMConnectionService._create_client(config)
        try:
            page = await client.models.list()
            model_ids = sorted(
                {
                    model.id.strip()
                    for model in page.data
                    if isinstance(model.id, str) and model.id.strip()
                },
                key=str.casefold,
            )
            return LLMModelListRead(models=model_ids, count=len(model_ids))
        except OpenAIError as exc:
            LLMConnectionService._raise_openai_error(exc, action="获取模型列表")
        finally:
            with suppress(Exception):
                await client.close()

    @staticmethod
    async def test_connection(
        session: AsyncSession,
        payload: LLMConnectionTestRequest,
    ) -> LLMConnectionTestRead:
        config = await LLMConnectionService._resolve_config(session, payload)
        client = LLMConnectionService._create_client(config)
        started_at = perf_counter()
        try:
            # 使用与解析 Skill 相同的 Chat Completions 路径，确认模型确实可调用。
            response = await client.chat.completions.create(
                model=payload.model,
                messages=[
                    {
                        "role": "user",
                        "content": "这是连接测试。请只回复 OK。",
                    }
                ],
            )
            if not response.choices:
                raise AppException(
                    "模型连接成功，但没有返回有效结果",
                    code=50219,
                    status_code=502,
                )
            latency_ms = max(1, round((perf_counter() - started_at) * 1000))
            return LLMConnectionTestRead(
                model=payload.model,
                latency_ms=latency_ms,
            )
        except OpenAIError as exc:
            LLMConnectionService._raise_openai_error(exc, action="测试模型连接")
        finally:
            with suppress(Exception):
                await client.close()

    @staticmethod
    async def _resolve_config(
        session: AsyncSession,
        payload: LLMConnectionBase,
    ) -> LLMConnectionConfig:
        api_key = (
            payload.api_key.get_secret_value()
            if payload.api_key is not None
            else None
        )
        if api_key and looks_like_masked_api_key(api_key):
            api_key = None

        if not api_key and payload.provider_id is not None:
            provider = await LLMProviderService.get_provider(
                session,
                payload.provider_id,
            )
            if payload.base_url != provider.base_url.rstrip("/"):
                raise AppException(
                    "服务地址已修改，请重新输入 API Key 后再获取模型或测试连接",
                    code=42233,
                    status_code=422,
                )
            api_key = provider.api_key

        if not api_key:
            raise AppException(
                "请先填写 API Key；编辑已有提供商时可以保留为空",
                code=42232,
                status_code=422,
            )

        return LLMConnectionConfig(
            provider_id=payload.provider_id,
            base_url=payload.base_url,
            api_key=api_key,
            timeout_seconds=payload.timeout_seconds,
        )

    @staticmethod
    def _create_client(config: LLMConnectionConfig) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )

    @staticmethod
    def _raise_openai_error(exc: OpenAIError, *, action: str) -> NoReturn:
        if isinstance(exc, AuthenticationError):
            raise AppException(
                "大模型鉴权失败，请检查 API Key",
                code=50213,
                status_code=502,
            ) from exc
        if isinstance(exc, PermissionDeniedError):
            raise AppException(
                "当前 API Key 没有访问该服务或模型的权限",
                code=50214,
                status_code=502,
            ) from exc
        if isinstance(exc, RateLimitError):
            raise AppException(
                "大模型服务请求过于频繁或额度不足",
                code=50215,
                status_code=502,
            ) from exc
        if isinstance(exc, APITimeoutError):
            raise AppException(
                f"{action}超时，请检查服务状态或提高超时时间",
                code=50401,
                status_code=504,
            ) from exc
        if isinstance(exc, APIConnectionError):
            raise AppException(
                "无法连接大模型服务，请检查服务地址和网络",
                code=50216,
                status_code=502,
            ) from exc
        if isinstance(exc, BadRequestError):
            raise AppException(
                f"{action}失败，请检查模型名称及 OpenAI 兼容性",
                code=50218,
                status_code=502,
            ) from exc
        if isinstance(exc, APIStatusError):
            if exc.status_code == 404 and action == "获取模型列表":
                message = "该服务不支持获取模型列表，请手动输入模型名称"
            else:
                message = f"{action}失败，服务返回 HTTP {exc.status_code}"
            raise AppException(message, code=50217, status_code=502) from exc
        raise AppException(
            f"{action}失败，请检查提供商配置",
            code=50217,
            status_code=502,
        ) from exc
