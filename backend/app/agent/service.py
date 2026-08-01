import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
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
from app.models.parse_result import ParseResultStatus, TaskParseResult
from app.models.task import Task, TaskStatus
from app.schemas.agent import (
    AgentConfirmInput,
    AgentMatchSummary,
    AgentParseSummary,
    AgentRejectInput,
    AgentStatusRead,
)
from app.schemas.skills.match import MatchReport
from app.schemas.skills.parse import ParseResult
from app.services.template_service import TemplateService
from app.skills.llm import TenderLLMClient
from app.skills.prompt_loader import PROMPTS


logger = logging.getLogger(__name__)

_CHAT_HISTORY_KEY = "chat_history"
_CHAT_HISTORY_LIMIT = 12
_CHAT_CONTEXT_LIMIT = 20000


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
    async def reject_and_reparse(
        task_id: uuid.UUID,
        payload: AgentRejectInput,
    ) -> AgentStatusRead:
        """驳回指定解析结果，并立即重新解析作为新版本追加。"""

        async with AsyncSessionFactory() as session:
            task = await AgentService._get_task_for_update(session, task_id)
            parse_record = await session.get(TaskParseResult, payload.parse_result_id)
            if parse_record is None:
                raise NotFoundException("解析结果不存在")
            if parse_record.task_id != task_id:
                raise AppException(
                    "解析结果不属于当前任务",
                    code=40933,
                    status_code=409,
                )
            run = await AgentService._get_latest_run(session, task_id)
            if run is not None and run.status == AgentRunStatus.RUNNING:
                raise ConflictException("Agent 正在执行中，暂不能驳回解析结果")

            was_waiting = (
                run is not None and run.status == AgentRunStatus.WAITING_CONFIRM
            )
            thread_id = run.thread_id if run is not None else None
            if was_waiting:
                run.current_step = AgentStep.CANCELLED
                run.status = AgentRunStatus.CANCELLED
                run.error_message = None
                run.completed_at = datetime.now(timezone.utc)
                task.status = TaskStatus.CREATED

            parse_record.is_rejected = True
            parse_record.reject_reason = payload.reason
            if "template_id" in payload.model_fields_set:
                if payload.template_id is not None:
                    await TemplateService.ensure_exists(
                        session,
                        payload.template_id,
                    )
                # 显式选择模板后同步到任务，后续重新解析沿用同一选择。
                task.parse_template_id = payload.template_id
            await session.commit()

        if was_waiting and thread_id is not None:
            try:
                await agent_graph_manager.delete_thread(thread_id)
            except Exception:
                logger.exception(
                    "驳回后清理 Agent checkpoint 失败，thread_id=%s",
                    thread_id,
                )
        return await AgentService.start(task_id)

    @staticmethod
    async def chat(
        task_id: uuid.UUID,
        question: str,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """基于最新解析结果与原文，在当前 Agent 会话内继续对话。"""

        async with AsyncSessionFactory() as session:
            await AgentService._get_task(session, task_id)
            run = await AgentService._get_latest_run(session, task_id)
            if run is None:
                raise NotFoundException("该任务尚未启动 Agent 流程")
            statement = (
                select(TaskParseResult)
                .where(
                    TaskParseResult.task_id == task_id,
                    TaskParseResult.status == ParseResultStatus.SUCCESS,
                )
                .order_by(
                    TaskParseResult.created_at.desc(),
                    TaskParseResult.id.desc(),
                )
                .limit(1)
            )
            latest = await session.scalar(statement)
            if latest is None or latest.result_json is None:
                raise ConflictException(
                    "该任务还没有可用的解析结果，请先完成一次解析"
                )
            run_id = run.id
            history = list((run.extra or {}).get(_CHAT_HISTORY_KEY) or [])

        context = AgentService._build_chat_context(
            latest.result_json,
            latest.source_texts,
        )
        answer = await TenderLLMClient().chat(
            system_prompt=PROMPTS["chat_system"].content,
            history=history[-(_CHAT_HISTORY_LIMIT - 2) :],
            context=context,
            question=question,
            task_id=task_id,
            on_delta=on_delta,
        )

        async with AsyncSessionFactory() as session:
            run = await session.get(AgentRun, run_id)
            if run is not None:
                extra = dict(run.extra or {})
                messages = list(extra.get(_CHAT_HISTORY_KEY) or [])
                messages.extend(
                    [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                )
                extra[_CHAT_HISTORY_KEY] = messages[-_CHAT_HISTORY_LIMIT:]
                run.extra = extra
                await session.commit()
        return answer

    @staticmethod
    def _build_chat_context(
        result_json: dict[str, Any],
        source_texts: list[dict[str, Any]] | None,
    ) -> str:
        """把解析结果与原文整理成对话可用的上下文文本。"""

        lines: list[str] = []
        try:
            result = ParseResult.model_validate(result_json)
        except ValidationError:
            result = None
        if result is not None:
            lines.append("=== 结构化解析结果 ===")
            for section in result.template.sections:
                lines.append(f"[{section.title}]")
                value = result.data.get(section.id)
                lines.append(
                    json.dumps(value, ensure_ascii=False, indent=1)[:2000]
                )
        if source_texts:
            lines.append("")
            lines.append("=== 标书原文（截取） ===")
            for item in source_texts[:3]:
                filename = str(item.get("filename") or "未命名文件")
                text = str(item.get("text") or "")[:6000]
                lines.append(f"--- {filename} ---")
                lines.append(text)
        return "\n".join(lines)[:_CHAT_CONTEXT_LIMIT]

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
