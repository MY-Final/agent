import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.service import AgentService
from app.core.llm_stream import reset_llm_stream_handlers, set_llm_stream_handlers
from app.core.response import ApiResponse, success_response
from app.core.sse import SSE_HEADERS, EventBridge, sse_event, stream_error_message
from app.schemas.agent import AgentStatusRead
from app.schemas.agent import (
    AgentChatInput,
    AgentConfirmInput,
    AgentRejectInput,
    AgentStatusRead,
)


router = APIRouter(tags=["任务分析 Agent"])


@router.post(
    "/tasks/{task_id}/agent/chat/stream",
    response_model=None,
    summary="与当前任务 Agent 对话（SSE）",
)
async def chat_agent_stream(
    task_id: uuid.UUID,
    payload: AgentChatInput,
) -> StreamingResponse:
    """基于最新解析结果与原文流式回答；SSE 事件：stage / delta / result / error。"""

    async def event_source() -> AsyncIterator[str]:
        bridge = EventBridge()
        tokens = set_llm_stream_handlers(bridge.emit_delta, bridge.emit_stage)
        task: asyncio.Task[str] | None = None
        try:
            await bridge.emit_stage(
                "chat",
                "正在基于当前解析结果回答…",
            )
            task = asyncio.create_task(
                AgentService.chat(
                    task_id,
                    payload.question,
                    on_delta=bridge.emit_delta,
                )
            )
            async for event in bridge.pump(task):
                yield sse_event(event)
            answer = task.result()
            await bridge.emit_stage("done", "回答完成")
            yield sse_event({"type": "result", "data": {"answer": answer}})
        except Exception as exc:
            code, message = stream_error_message(exc)
            yield sse_event({"type": "error", "code": code, "message": message})
        finally:
            if task is not None and not task.done():
                task.cancel()
            reset_llm_stream_handlers(tokens)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/tasks/{task_id}/agent/start/stream",
    response_model=None,
    summary="流式启动任务分析 Agent（SSE）",
)
async def start_agent_stream(task_id: uuid.UUID) -> StreamingResponse:
    """SSE 事件流：stage（Agent 阶段）/ delta（大模型增量）/ result / error。"""

    async def event_source() -> AsyncIterator[str]:
        bridge = EventBridge()
        tokens = set_llm_stream_handlers(bridge.emit_delta, bridge.emit_stage)
        task: asyncio.Task[AgentStatusRead] | None = None
        try:
            await bridge.emit_stage(
                "agent",
                "Agent 流程已启动，正在解析标书…",
            )
            task = asyncio.create_task(AgentService.start(task_id))
            async for event in bridge.pump(task):
                yield sse_event(event)
            result = task.result()
            message = (
                "解析完成，请确认解析结果"
                if result.is_waiting_confirmation
                else "Agent 流程执行结束"
            )
            await bridge.emit_stage("done", message)
            yield sse_event(
                {"type": "result", "data": result.model_dump(mode="json")}
            )
        except Exception as exc:
            code, message = stream_error_message(exc)
            yield sse_event({"type": "error", "code": code, "message": message})
        finally:
            if task is not None and not task.done():
                task.cancel()
            reset_llm_stream_handlers(tokens)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/tasks/{task_id}/agent/start",
    response_model=ApiResponse[AgentStatusRead],
    summary="启动任务分析 Agent",
)
async def start_agent(task_id: uuid.UUID) -> ApiResponse[AgentStatusRead]:
    result = await AgentService.start(task_id)
    if result.is_waiting_confirmation:
        message = "Agent 已完成解析，等待人工确认"
    elif result.status.value == "failed":
        message = "Agent 执行失败，请查看错误信息"
    else:
        message = "Agent 启动完成，请查看当前状态"
    return success_response(result, msg=message)


@router.get(
    "/tasks/{task_id}/agent/status",
    response_model=ApiResponse[AgentStatusRead],
    summary="查询任务分析 Agent 状态",
)
async def get_agent_status(task_id: uuid.UUID) -> ApiResponse[AgentStatusRead]:
    result = await AgentService.get_status(task_id)
    return success_response(result, msg="Agent 状态查询成功")


@router.post(
    "/tasks/{task_id}/agent/confirm",
    response_model=ApiResponse[AgentStatusRead],
    summary="确认解析结果并继续资质匹配",
)
async def confirm_agent(
    task_id: uuid.UUID,
    payload: AgentConfirmInput | None = None,
) -> ApiResponse[AgentStatusRead]:
    result = await AgentService.confirm(task_id, payload or AgentConfirmInput())
    if result.status.value == "completed":
        message = "Agent 分析流程已完成"
    elif result.status.value == "failed":
        message = "Agent 执行失败，请查看错误信息"
    else:
        message = "Agent 已继续执行"
    return success_response(result, msg=message)


@router.post(
    "/tasks/{task_id}/agent/cancel",
    response_model=ApiResponse[AgentStatusRead],
    summary="取消等待确认的 Agent 流程",
)
async def cancel_agent(task_id: uuid.UUID) -> ApiResponse[AgentStatusRead]:
    result = await AgentService.cancel(task_id)
    return success_response(result, msg="Agent 流程已取消")


@router.post(
    "/tasks/{task_id}/agent/reject-and-reparse",
    response_model=ApiResponse[AgentStatusRead],
    summary="驳回解析结果并立即重新解析",
)
async def reject_and_reparse_agent(
    task_id: uuid.UUID,
    payload: AgentRejectInput,
) -> ApiResponse[AgentStatusRead]:
    result = await AgentService.reject_and_reparse(task_id, payload)
    message = (
        "已驳回原解析结果并开始重新解析"
        if result.status.value != "failed"
        else "重新解析启动失败，请查看错误信息"
    )
    return success_response(result, msg=message)
