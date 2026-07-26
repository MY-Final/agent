import logging
import uuid
from datetime import datetime, timezone
from langgraph.types import Command
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import agent_graph_manager
from app.agent.state import AgentState
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppException, ConflictException, NotFoundException
from app.models.agent_run import AgentRun, AgentRunStatus, AgentStep
from app.models.match_result import TaskMatchResult
from app.models.parse_result import TaskParseResult
from app.models.task import Task, TaskStatus
from app.schemas.agent import (
    AgentConfirmInput,
    AgentMatchSummary,
    AgentParseSummary,
    AgentStatusRead,
)
from app.schemas.skills.match import MatchReport
from app.schemas.skills.parse import ParseResult


logger = logging.getLogger(__name__)


class AgentService:
    @staticmethod
    async def start(task_id: uuid.UUID) -> AgentStatusRead:
        run_id = uuid.uuid4()
        thread_id = run_id.hex
        async with AsyncSessionFactory() as session:
            task = await AgentService._get_task_for_update(session, task_id)
            active_run = await AgentService._get_latest_run(session, task_id)
            if active_run is not None and active_run.status in {
                AgentRunStatus.RUNNING,
                AgentRunStatus.WAITING_CONFIRM,
            }:
                raise ConflictException("该任务已有正在运行或等待确认的 Agent 流程")

            run = AgentRun(
                id=run_id,
                task_id=task.id,
                thread_id=thread_id,
                current_step=AgentStep.PARSE,
                status=AgentRunStatus.RUNNING,
                extra={},
            )
            session.add(run)
            await session.commit()

        initial_state: AgentState = {
            "agent_run_id": str(run_id),
            "task_id": str(task_id),
            "current_step": AgentStep.PARSE.value,
            "parse_result_id": None,
            "match_result_id": None,
            "error_message": None,
            "user_confirmed": False,
            "confirmation_note": None,
            "extra": {},
        }
        try:
            await agent_graph_manager.graph.ainvoke(
                initial_state,
                AgentService._graph_config(thread_id),
            )
        except Exception as exc:
            await AgentService._mark_invocation_failed(run_id, task_id, exc)
            raise AppException(
                "Agent 启动失败，请查看状态或服务日志",
                code=50041,
                status_code=500,
            ) from exc
        return await AgentService._get_status_by_run_id(run_id)

    @staticmethod
    async def get_status(task_id: uuid.UUID) -> AgentStatusRead:
        async with AsyncSessionFactory() as session:
            await AgentService._get_task(session, task_id)
            run = await AgentService._get_latest_run(session, task_id)
            if run is None:
                raise NotFoundException("该任务尚未启动 Agent 流程")
            run_id = run.id
        return await AgentService._get_status_by_run_id(run_id)

    @staticmethod
    async def confirm(
        task_id: uuid.UUID,
        payload: AgentConfirmInput,
    ) -> AgentStatusRead:
        async with AsyncSessionFactory() as session:
            await AgentService._get_task_for_update(session, task_id)
            run = await AgentService._get_latest_run(
                session,
                task_id,
                for_update=True,
            )
            if run is None:
                raise NotFoundException("该任务尚未启动 Agent 流程")
            if (
                run.status != AgentRunStatus.WAITING_CONFIRM
                or run.current_step != AgentStep.WAIT_CONFIRM
            ):
                raise ConflictException("当前 Agent 流程不处于等待确认状态")
            run_id = run.id
            thread_id = run.thread_id
            config = AgentService._graph_config(thread_id)
            snapshot = await agent_graph_manager.graph.aget_state(config)
            if "human_confirm" not in snapshot.next:
                raise ConflictException("Agent checkpoint 未处于人工确认节点")

            # 先占用本次恢复，避免桌面端重复点击导致同一 checkpoint 被并发恢复。
            run.current_step = AgentStep.MATCH
            run.status = AgentRunStatus.RUNNING
            run.user_confirmed = True
            run.confirmation_note = payload.remark
            await session.commit()

        try:
            await agent_graph_manager.graph.ainvoke(
                Command(resume={"confirmed": True, "remark": payload.remark}),
                config,
            )
        except Exception as exc:
            await AgentService._mark_invocation_failed(run_id, task_id, exc)
            raise AppException(
                "Agent 确认后继续执行失败，请查看状态或服务日志",
                code=50042,
                status_code=500,
            ) from exc
        return await AgentService._get_status_by_run_id(run_id)

    @staticmethod
    async def cancel(task_id: uuid.UUID) -> AgentStatusRead:
        async with AsyncSessionFactory() as session:
            task = await AgentService._get_task_for_update(session, task_id)
            run = await AgentService._get_latest_run(session, task_id)
            if run is None:
                raise NotFoundException("该任务尚未启动 Agent 流程")
            if (
                run.status != AgentRunStatus.WAITING_CONFIRM
                or run.current_step != AgentStep.WAIT_CONFIRM
            ):
                raise ConflictException("当前仅支持取消等待人工确认的 Agent 流程")

            run.current_step = AgentStep.CANCELLED
            run.status = AgentRunStatus.CANCELLED
            run.error_message = None
            run.completed_at = datetime.now(timezone.utc)
            task.status = TaskStatus.CREATED
            run_id = run.id
            thread_id = run.thread_id
            await session.commit()

        try:
            await agent_graph_manager.delete_thread(thread_id)
        except Exception:
            # 业务状态已经取消；checkpoint 清理失败不应让前端误以为取消失败。
            logger.exception("清理已取消 Agent 的 checkpoint 失败，thread_id=%s", thread_id)
        return await AgentService._get_status_by_run_id(run_id)

    @staticmethod
    async def _get_status_by_run_id(run_id: uuid.UUID) -> AgentStatusRead:
        async with AsyncSessionFactory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                raise NotFoundException("Agent 运行记录不存在")
            task = await AgentService._get_task(session, run.task_id)
            parse_summary = await AgentService._get_parse_summary(
                session,
                run.parse_result_id,
            )
            match_summary = await AgentService._get_match_summary(
                session,
                run.match_result_id,
            )
            return AgentStatusRead(
                run_id=run.id,
                task_id=run.task_id,
                thread_id=run.thread_id,
                current_step=run.current_step,
                status=run.status,
                task_status=task.status,
                is_waiting_confirmation=(
                    run.status == AgentRunStatus.WAITING_CONFIRM
                    and run.current_step == AgentStep.WAIT_CONFIRM
                ),
                user_confirmed=run.user_confirmed,
                confirmation_note=run.confirmation_note,
                parse_result_id=run.parse_result_id,
                match_result_id=run.match_result_id,
                parse_summary=parse_summary,
                match_summary=match_summary,
                error_message=run.error_message,
                extra=run.extra,
                started_at=run.started_at,
                completed_at=run.completed_at,
                created_at=run.created_at,
                updated_at=run.updated_at,
            )

    @staticmethod
    async def _get_parse_summary(
        session: AsyncSession,
        result_id: uuid.UUID | None,
    ) -> AgentParseSummary | None:
        if result_id is None:
            return None
        record = await session.get(TaskParseResult, result_id)
        if record is None or record.result_json is None:
            return None
        try:
            result = ParseResult.model_validate(record.result_json)
        except ValidationError:
            logger.warning("Agent 解析摘要校验失败，parse_result_id=%s", result_id)
            return None
        return AgentParseSummary(
            project_name=result.project_name,
            project_code=result.project_code,
            budget=result.budget,
            qualification_count=len(result.qualifications),
            raw_summary=result.raw_summary,
        )

    @staticmethod
    async def _get_match_summary(
        session: AsyncSession,
        result_id: uuid.UUID | None,
    ) -> AgentMatchSummary | None:
        if result_id is None:
            return None
        record = await session.get(TaskMatchResult, result_id)
        if record is None or record.result_json is None:
            return None
        try:
            result = MatchReport.model_validate(record.result_json)
        except ValidationError:
            logger.warning("Agent 匹配摘要校验失败，match_result_id=%s", result_id)
            return None
        return AgentMatchSummary(
            overall_match_score=result.overall_match_score,
            summary=result.summary,
            matched_count=len(result.matched_items),
            missing_count=len(result.missing_items),
            risk_count=len(result.risk_items),
        )

    @staticmethod
    async def _get_task(session: AsyncSession, task_id: uuid.UUID) -> Task:
        task = await session.get(Task, task_id)
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    async def _get_task_for_update(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> Task:
        statement = select(Task).where(Task.id == task_id).with_for_update()
        task = await session.scalar(statement)
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    async def _get_latest_run(
        session: AsyncSession,
        task_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AgentRun | None:
        statement = (
            select(AgentRun)
            .where(AgentRun.task_id == task_id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @staticmethod
    async def _mark_invocation_failed(
        run_id: uuid.UUID,
        task_id: uuid.UUID,
        exc: Exception,
    ) -> None:
        logger.error(
            "LangGraph 调用失败，run_id=%s",
            run_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        message = str(exc).strip()[:4000] or "LangGraph 执行异常"
        try:
            async with AsyncSessionFactory() as session:
                run = await session.get(AgentRun, run_id)
                task = await session.get(Task, task_id)
                if run is not None:
                    run.current_step = AgentStep.FAILED
                    run.status = AgentRunStatus.FAILED
                    run.error_message = message
                    run.completed_at = datetime.now(timezone.utc)
                if task is not None:
                    task.status = TaskStatus.FAILED
                await session.commit()
        except Exception:
            logger.exception("保存 LangGraph 调用失败状态时发生异常，run_id=%s", run_id)

    @staticmethod
    def _graph_config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}
