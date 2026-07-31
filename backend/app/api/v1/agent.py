import uuid

from fastapi import APIRouter

from app.agent.service import AgentService
from app.core.response import ApiResponse, success_response
from app.schemas.agent import AgentConfirmInput, AgentRejectInput, AgentStatusRead


router = APIRouter(tags=["任务分析 Agent"])


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
