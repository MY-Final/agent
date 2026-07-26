import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppException
from app.core.minio import minio_storage
from app.models.agent_run import AgentRun, AgentRunStatus, AgentStep
from app.models.task import Task, TaskStatus
from app.services.match_service import MatchService
from app.services.parse_service import ParseService


logger = logging.getLogger(__name__)


async def parse_node(state: AgentState) -> dict[str, Any]:
    """调用现有解析服务，并把流程推进到人工确认节点。"""

    task_id = uuid.UUID(state["task_id"])
    run_id = uuid.UUID(state["agent_run_id"])
    try:
        await _mark_running(run_id, AgentStep.PARSE)
        async with AsyncSessionFactory() as session:
            record = await ParseService.parse_task(session, minio_storage, task_id)

        async with AsyncSessionFactory() as session:
            run = await _require_run(session, run_id)
            run.parse_result_id = record.id
            run.current_step = AgentStep.WAIT_CONFIRM
            run.status = AgentRunStatus.WAITING_CONFIRM
            run.error_message = None
            await session.commit()

        logger.info("Agent 标书解析完成，task_id=%s，run_id=%s", task_id, run_id)
        return {
            "current_step": AgentStep.WAIT_CONFIRM.value,
            "parse_result_id": str(record.id),
            "error_message": None,
        }
    except Exception as exc:
        message = _error_message(exc, "标书解析失败")
        logger.exception("Agent 解析节点失败，task_id=%s，run_id=%s", task_id, run_id)
        await _mark_failed(run_id, task_id, message)
        return {
            "current_step": AgentStep.FAILED.value,
            "error_message": message,
        }


def human_confirm_node(state: AgentState) -> dict[str, Any]:
    """通过 LangGraph interrupt 暂停；确认接口使用 Command 恢复。"""

    confirmation = interrupt(
        {
            "message": "标书解析已完成，请确认后继续资质匹配",
            "task_id": state["task_id"],
            "parse_result_id": state.get("parse_result_id"),
        }
    )
    remark = confirmation.get("remark") if isinstance(confirmation, dict) else None
    return {
        "current_step": AgentStep.MATCH.value,
        "user_confirmed": True,
        "confirmation_note": remark,
    }


async def match_node(state: AgentState) -> dict[str, Any]:
    """使用本次 Agent 生成的解析结果执行确定性资质匹配。"""

    task_id = uuid.UUID(state["task_id"])
    run_id = uuid.UUID(state["agent_run_id"])
    parse_result_id_value = state.get("parse_result_id")
    if parse_result_id_value is None:
        message = "Agent 状态中缺少解析结果，无法执行资质匹配"
        await _mark_failed(run_id, task_id, message)
        return {
            "current_step": AgentStep.FAILED.value,
            "error_message": message,
        }

    try:
        await _mark_match_started(
            run_id,
            state.get("confirmation_note"),
        )
        parse_result_id = uuid.UUID(parse_result_id_value)
        async with AsyncSessionFactory() as session:
            record = await MatchService.match_parse_result(
                session,
                parse_result_id,
                task_id=task_id,
            )

        async with AsyncSessionFactory() as session:
            run = await _require_run(session, run_id)
            task = await _require_task(session, task_id)
            run.match_result_id = record.id
            run.current_step = AgentStep.COMPLETED
            run.status = AgentRunStatus.COMPLETED
            run.user_confirmed = True
            run.error_message = None
            run.completed_at = datetime.now(timezone.utc)
            task.status = TaskStatus.COMPLETED
            await session.commit()

        logger.info("Agent 资质匹配完成，task_id=%s，run_id=%s", task_id, run_id)
        return {
            "current_step": AgentStep.COMPLETED.value,
            "match_result_id": str(record.id),
            "user_confirmed": True,
            "error_message": None,
        }
    except Exception as exc:
        message = _error_message(exc, "资质匹配失败")
        logger.exception("Agent 匹配节点失败，task_id=%s，run_id=%s", task_id, run_id)
        await _mark_failed(run_id, task_id, message)
        return {
            "current_step": AgentStep.FAILED.value,
            "error_message": message,
        }


async def end_node(state: AgentState) -> dict[str, Any]:
    """显式结束节点，为后续接入报告生成等节点保留清晰扩展点。"""

    logger.info(
        "Agent 流程结束，task_id=%s，run_id=%s",
        state["task_id"],
        state["agent_run_id"],
    )
    return {"current_step": AgentStep.COMPLETED.value}


async def _mark_running(run_id: uuid.UUID, step: AgentStep) -> None:
    async with AsyncSessionFactory() as session:
        run = await _require_run(session, run_id)
        run.current_step = step
        run.status = AgentRunStatus.RUNNING
        run.error_message = None
        await session.commit()


async def _mark_match_started(run_id: uuid.UUID, note: str | None) -> None:
    async with AsyncSessionFactory() as session:
        run = await _require_run(session, run_id)
        run.current_step = AgentStep.MATCH
        run.status = AgentRunStatus.RUNNING
        run.user_confirmed = True
        run.confirmation_note = note
        run.error_message = None
        await session.commit()


async def _mark_failed(
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    message: str,
) -> None:
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
        logger.exception("保存 Agent 失败状态时发生异常，run_id=%s", run_id)


async def _require_run(session: AsyncSession, run_id: uuid.UUID) -> AgentRun:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise RuntimeError("Agent 运行记录不存在")
    return run


async def _require_task(session: AsyncSession, task_id: uuid.UUID) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise RuntimeError("任务不存在")
    return task


def _error_message(exc: Exception, prefix: str) -> str:
    if isinstance(exc, AppException):
        return exc.message
    message = str(exc).strip()
    return f"{prefix}：{message[:3900] if message else '未知错误'}"
