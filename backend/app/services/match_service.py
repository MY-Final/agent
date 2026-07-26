import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFoundException
from app.models.match_result import MatchResultStatus, TaskMatchResult
from app.models.parse_result import ParseResultStatus, TaskParseResult
from app.models.task import Task, TaskStatus
from app.schemas.skills.match import MatchInput
from app.schemas.skills.parse import ParseResult
from app.services.qualification_service import QualificationService
from app.skills.match_qualification import CompanyKnowledgeBase, MatchQualificationSkill


logger = logging.getLogger(__name__)


class MatchService:
    @staticmethod
    async def match_from_input(
        session: AsyncSession,
        payload: MatchInput,
    ) -> TaskMatchResult:
        if payload.task_id is not None:
            return await MatchService.match_task(session, payload.task_id)

        parse_record = await MatchService._get_parse_result(
            session,
            payload.parse_result_id,
        )
        return await MatchService._execute(
            session=session,
            parse_record=parse_record,
            task_id=parse_record.task_id,
            update_task_status=parse_record.task_id is not None,
        )

    @staticmethod
    async def match_task(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskMatchResult:
        await MatchService._get_task(session, task_id)
        parse_record = await MatchService._get_latest_success_parse_result(
            session,
            task_id,
        )
        return await MatchService._execute(
            session=session,
            parse_record=parse_record,
            task_id=task_id,
            update_task_status=True,
        )

    @staticmethod
    async def get_latest_result(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskMatchResult:
        await MatchService._get_task(session, task_id)
        statement = (
            select(TaskMatchResult)
            .where(TaskMatchResult.task_id == task_id)
            .order_by(TaskMatchResult.created_at.desc(), TaskMatchResult.id.desc())
            .limit(1)
        )
        record = await session.scalar(statement)
        if record is None:
            raise NotFoundException("该任务暂无资质匹配结果")
        return record

    @staticmethod
    async def _execute(
        *,
        session: AsyncSession,
        parse_record: TaskParseResult,
        task_id: uuid.UUID | None,
        update_task_status: bool,
    ) -> TaskMatchResult:
        if update_task_status and task_id is not None:
            await MatchService._set_task_status(session, task_id, TaskStatus.ANALYZING)

        try:
            if parse_record.result_json is None:
                raise ValueError("标书解析记录中没有结构化结果")
            parse_result = ParseResult.model_validate(parse_record.result_json)
            certificates, performances, personnel, companies = (
                await QualificationService.get_knowledge_base(session)
            )
            report = MatchQualificationSkill().run(
                parse_result,
                CompanyKnowledgeBase(
                    certificates=certificates,
                    performances=performances,
                    personnel=personnel,
                    companies=companies,
                ),
            )
            record = TaskMatchResult(
                task_id=task_id,
                parse_result_id=parse_record.id,
                result_json=report.model_dump(mode="json"),
                status=MatchResultStatus.SUCCESS,
                error_message=None,
            )
            session.add(record)
            if update_task_status and task_id is not None:
                task = await MatchService._get_task(session, task_id)
                task.status = TaskStatus.WAITING_CONFIRM
            await session.commit()
            await session.refresh(record)
            return record
        except Exception as exc:
            if isinstance(exc, (AppException, ValueError)):
                logger.warning(
                    "资质匹配失败，parse_result_id=%s：%s",
                    parse_record.id,
                    exc,
                )
            else:
                logger.exception(
                    "资质匹配失败，parse_result_id=%s",
                    parse_record.id,
                )
            await session.rollback()
            error_message = MatchService._error_message(exc)
            failure_record = TaskMatchResult(
                task_id=task_id,
                parse_result_id=parse_record.id,
                result_json=None,
                status=MatchResultStatus.FAILED,
                error_message=error_message,
            )
            session.add(failure_record)
            if update_task_status and task_id is not None:
                task = await MatchService._get_task(session, task_id)
                task.status = TaskStatus.FAILED
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("保存资质匹配失败记录时发生异常")

            if isinstance(exc, AppException):
                raise
            if isinstance(exc, ValueError):
                raise AppException(error_message, code=42231, status_code=422) from exc
            raise AppException(
                f"资质匹配失败：{error_message}",
                code=50031,
                status_code=500,
            ) from exc

    @staticmethod
    async def _get_latest_success_parse_result(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskParseResult:
        statement = (
            select(TaskParseResult)
            .where(
                TaskParseResult.task_id == task_id,
                TaskParseResult.status == ParseResultStatus.SUCCESS,
                TaskParseResult.result_json.is_not(None),
            )
            .order_by(TaskParseResult.created_at.desc(), TaskParseResult.id.desc())
            .limit(1)
        )
        record = await session.scalar(statement)
        if record is None:
            raise NotFoundException("该任务没有成功的标书解析结果，请先完成解析")
        return record

    @staticmethod
    async def _get_parse_result(
        session: AsyncSession,
        parse_result_id: uuid.UUID | None,
    ) -> TaskParseResult:
        if parse_result_id is None:
            raise AppException("缺少 parse_result_id", code=40031, status_code=400)
        record = await session.get(TaskParseResult, parse_result_id)
        if record is None:
            raise NotFoundException("标书解析结果不存在")
        if record.status != ParseResultStatus.SUCCESS or record.result_json is None:
            raise AppException(
                "只能对解析成功且包含结构化结果的记录执行匹配",
                code=40931,
                status_code=409,
            )
        return record

    @staticmethod
    async def _get_task(session: AsyncSession, task_id: uuid.UUID) -> Task:
        task = await session.get(Task, task_id)
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    async def _set_task_status(
        session: AsyncSession,
        task_id: uuid.UUID,
        status: TaskStatus,
    ) -> None:
        task = await MatchService._get_task(session, task_id)
        task.status = status
        await session.commit()

    @staticmethod
    def _error_message(exc: Exception) -> str:
        if isinstance(exc, AppException):
            return exc.message
        message = str(exc).strip()
        return message[:4000] if message else "未知匹配错误"
