import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppException, ConflictException, NotFoundException
from app.models.llm_provider import LLMProvider
from app.schemas.llm_provider import LLMProviderCreate, LLMProviderUpdate
from app.utils.secrets import looks_like_masked_api_key


@dataclass(slots=True, frozen=True)
class LLMRuntimeConfig:
    """内部调用使用的完整配置，不应直接作为 API 响应返回。"""

    source: Literal["database", "env"]
    provider_id: uuid.UUID | None
    provider_name: str | None
    provider_type: str
    base_url: str | None
    api_key: str | None
    default_model: str
    timeout_seconds: float
    extra_config: dict[str, Any]


class LLMProviderService:
    @staticmethod
    async def list_providers(session: AsyncSession) -> list[LLMProvider]:
        statement = select(LLMProvider).order_by(
            LLMProvider.is_default.desc(),
            LLMProvider.created_at.desc(),
        )
        return list((await session.scalars(statement)).all())

    @staticmethod
    async def create_provider(
        session: AsyncSession,
        payload: LLMProviderCreate,
    ) -> LLMProvider:
        values = payload.model_dump(exclude={"api_key"})
        values["api_key"] = payload.api_key.get_secret_value()
        record = LLMProvider(**values)

        if record.is_default:
            await LLMProviderService._clear_default(session)
        session.add(record)
        await LLMProviderService._commit(session, "大模型提供商创建失败")
        await session.refresh(record)
        return record

    @staticmethod
    async def get_provider(
        session: AsyncSession,
        provider_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> LLMProvider:
        statement = select(LLMProvider).where(LLMProvider.id == provider_id)
        if for_update:
            statement = statement.with_for_update()
        record = await session.scalar(statement)
        if record is None:
            raise NotFoundException("大模型提供商不存在")
        return record

    @staticmethod
    async def update_provider(
        session: AsyncSession,
        provider_id: uuid.UUID,
        payload: LLMProviderUpdate,
    ) -> LLMProvider:
        record = await LLMProviderService.get_provider(
            session,
            provider_id,
            for_update=True,
        )
        values = payload.model_dump(exclude_unset=True, exclude={"api_key"})

        # 空值或前端回传的脱敏值都不会覆盖数据库中的真实密钥。
        if "api_key" in payload.model_fields_set and payload.api_key is not None:
            api_key = payload.api_key.get_secret_value()
            if api_key and not looks_like_masked_api_key(api_key):
                values["api_key"] = api_key

        enabled_after_update = values.get("is_enabled", record.is_enabled)
        default_after_update = values.get("is_default", record.is_default)
        if values.get("is_default") is True and not enabled_after_update:
            raise AppException(
                "禁用的提供商不能设为默认提供商",
                code=42231,
                status_code=422,
            )

        if values.get("is_default") is True:
            await LLMProviderService._clear_default(session)
        elif not enabled_after_update and default_after_update:
            # 禁用当前默认项时自动取消默认，后续调用将回退到 .env。
            values["is_default"] = False

        for field, value in values.items():
            setattr(record, field, value)

        await LLMProviderService._commit(session, "大模型提供商更新失败")
        await session.refresh(record)
        return record

    @staticmethod
    async def delete_provider(
        session: AsyncSession,
        provider_id: uuid.UUID,
    ) -> None:
        record = await LLMProviderService.get_provider(
            session,
            provider_id,
            for_update=True,
        )
        if record.is_default:
            raise ConflictException("当前默认提供商不能删除，请先切换默认提供商")
        await session.delete(record)
        await session.commit()

    @staticmethod
    async def set_default(
        session: AsyncSession,
        provider_id: uuid.UUID,
    ) -> LLMProvider:
        record = await LLMProviderService.get_provider(
            session,
            provider_id,
            for_update=True,
        )
        if not record.is_enabled:
            raise ConflictException("禁用的提供商不能设为默认提供商")

        await LLMProviderService._clear_default(session)
        record.is_default = True
        await LLMProviderService._commit(session, "设置默认提供商失败")
        await session.refresh(record)
        return record

    @staticmethod
    async def get_current_config(session: AsyncSession) -> LLMRuntimeConfig:
        statement = (
            select(LLMProvider)
            .where(
                LLMProvider.is_default.is_(True),
                LLMProvider.is_enabled.is_(True),
            )
            .limit(1)
        )
        record = await session.scalar(statement)
        if record is not None:
            return LLMRuntimeConfig(
                source="database",
                provider_id=record.id,
                provider_name=record.name,
                provider_type=record.provider_type,
                base_url=record.base_url,
                api_key=record.api_key,
                default_model=record.default_model,
                timeout_seconds=float(record.timeout_seconds),
                extra_config=dict(record.extra_config),
            )

        return LLMRuntimeConfig(
            source="env",
            provider_id=None,
            provider_name=None,
            provider_type="openai_compatible",
            base_url=settings.llm_base_url,
            api_key=(
                settings.llm_api_key.get_secret_value()
                if settings.llm_api_key is not None
                else None
            ),
            default_model=settings.llm_model_name,
            timeout_seconds=settings.llm_timeout_seconds,
            extra_config={},
        )

    @staticmethod
    async def _clear_default(session: AsyncSession) -> None:
        await session.execute(
            update(LLMProvider)
            .where(LLMProvider.is_default.is_(True))
            .values(is_default=False)
        )

    @staticmethod
    async def _commit(session: AsyncSession, message: str) -> None:
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ConflictException(
                f"{message}，可能存在并发默认配置冲突"
            ) from exc


async def get_current_llm_config(
    session: AsyncSession | None = None,
) -> LLMRuntimeConfig:
    """按“数据库默认提供商 > .env”优先级解析当前 LLM 配置。"""

    if session is not None:
        return await LLMProviderService.get_current_config(session)

    async with AsyncSessionFactory() as owned_session:
        return await LLMProviderService.get_current_config(owned_session)

