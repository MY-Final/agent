import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.parse_template import ParseTemplate as ParseTemplateORM
from app.schemas.parse_template import (
    ParseTemplateCreate,
    ParseTemplateRead,
    ParseTemplateUpdate,
    template_to_schema,
)
from app.schemas.skills.parse import ParseTemplate
from app.skills.parse_template import SEED_PARSE_TEMPLATE


logger = logging.getLogger(__name__)


class TemplateService:
    @staticmethod
    async def seed_default_if_empty(session: AsyncSession) -> None:
        """首次启动时写入内置默认模板，保证解析链路开箱可用。"""

        total = int(
            (
                await session.scalar(
                    select(func.count()).select_from(ParseTemplateORM)
                )
            )
            or 0
        )
        if total:
            return
        session.add(
            ParseTemplateORM(
                name="默认标书解析模板",
                description=(
                    "内置默认模板：项目概览、资格要求、评分办法、"
                    "关键时间、废标条款、其他要点"
                ),
                version=SEED_PARSE_TEMPLATE.version,
                sections=[
                    section.model_dump(mode="json")
                    for section in SEED_PARSE_TEMPLATE.sections
                ],
                is_default=True,
            )
        )
        await session.commit()
        logger.info("已写入默认解析模板 v%s", SEED_PARSE_TEMPLATE.version)

    @staticmethod
    async def list_templates(session: AsyncSession) -> list[ParseTemplateRead]:
        statement = select(ParseTemplateORM).order_by(
            ParseTemplateORM.is_default.desc(),
            ParseTemplateORM.created_at.asc(),
        )
        records = list((await session.scalars(statement)).all())
        return [ParseTemplateRead.from_record(record) for record in records]

    @staticmethod
    async def get(session: AsyncSession, template_id: uuid.UUID) -> ParseTemplateORM:
        record = await session.get(ParseTemplateORM, template_id)
        if record is None:
            raise NotFoundException("解析模板不存在")
        return record

    @staticmethod
    async def create(
        session: AsyncSession,
        payload: ParseTemplateCreate,
    ) -> ParseTemplateORM:
        if payload.is_default:
            await _clear_default(session)
        record = ParseTemplateORM(**payload.model_dump())
        session.add(record)
        await session.commit()
        return record

    @staticmethod
    async def update(
        session: AsyncSession,
        template_id: uuid.UUID,
        payload: ParseTemplateUpdate,
    ) -> ParseTemplateORM:
        record = await TemplateService.get(session, template_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("is_default"):
            await _clear_default(session)
        for field, value in data.items():
            setattr(record, field, value)
        await session.commit()
        return record

    @staticmethod
    async def delete(session: AsyncSession, template_id: uuid.UUID) -> None:
        record = await TemplateService.get(session, template_id)
        await session.delete(record)
        await session.commit()

    @staticmethod
    async def ensure_exists(session: AsyncSession, template_id: uuid.UUID) -> None:
        await TemplateService.get(session, template_id)

    @staticmethod
    async def resolve_parse_template(
        session: AsyncSession,
        template_id: uuid.UUID | None = None,
    ) -> tuple[ParseTemplate, uuid.UUID | None]:
        """解析使用的模板：任务指定 > 默认模板 > 内置种子模板。

        返回（模板外壳, 数据库模板 id）；走内置种子模板时 id 为 None，
        id 用于把解析结果和模板版本做溯源绑定。
        """

        if template_id is not None:
            record = await session.get(ParseTemplateORM, template_id)
            if record is not None:
                return template_to_schema(record), record.id
        default = await session.scalar(
            select(ParseTemplateORM)
            .where(ParseTemplateORM.is_default.is_(True))
            .limit(1)
        )
        if default is not None:
            return template_to_schema(default), default.id
        return SEED_PARSE_TEMPLATE, None


async def _clear_default(session: AsyncSession) -> None:
    await session.execute(
        update(ParseTemplateORM)
        .where(ParseTemplateORM.is_default.is_(True))
        .values(is_default=False)
    )
