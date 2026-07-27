import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.response import ApiResponse, success_response
from app.schemas.llm_provider import (
    CurrentLLMConfigRead,
    LLMConnectionTestRead,
    LLMConnectionTestRequest,
    LLMModelListRead,
    LLMModelListRequest,
    LLMProviderCreate,
    LLMProviderRead,
    LLMProviderUpdate,
)
from app.schemas.task import DeleteResult
from app.services.llm_connection_service import LLMConnectionService
from app.services.llm_provider_service import (
    LLMProviderService,
    get_current_llm_config,
)
from app.utils.secrets import mask_api_key


router = APIRouter(prefix="/settings/llm", tags=["系统设置 - 大模型"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/providers",
    response_model=ApiResponse[list[LLMProviderRead]],
    summary="获取大模型提供商列表",
)
async def list_providers(
    session: SessionDep,
) -> ApiResponse[list[LLMProviderRead]]:
    records = await LLMProviderService.list_providers(session)
    return success_response([LLMProviderRead.from_record(record) for record in records])


@router.post(
    "/providers",
    response_model=ApiResponse[LLMProviderRead],
    status_code=status.HTTP_201_CREATED,
    summary="新增大模型提供商",
)
async def create_provider(
    payload: LLMProviderCreate,
    session: SessionDep,
) -> ApiResponse[LLMProviderRead]:
    record = await LLMProviderService.create_provider(session, payload)
    return success_response(
        LLMProviderRead.from_record(record),
        msg="大模型提供商创建成功",
    )


@router.get(
    "/providers/{provider_id}",
    response_model=ApiResponse[LLMProviderRead],
    summary="获取大模型提供商详情",
)
async def get_provider(
    provider_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[LLMProviderRead]:
    record = await LLMProviderService.get_provider(session, provider_id)
    return success_response(LLMProviderRead.from_record(record))


@router.put(
    "/providers/{provider_id}",
    response_model=ApiResponse[LLMProviderRead],
    summary="更新大模型提供商",
)
async def update_provider(
    provider_id: uuid.UUID,
    payload: LLMProviderUpdate,
    session: SessionDep,
) -> ApiResponse[LLMProviderRead]:
    record = await LLMProviderService.update_provider(session, provider_id, payload)
    return success_response(
        LLMProviderRead.from_record(record),
        msg="大模型提供商更新成功",
    )


@router.delete(
    "/providers/{provider_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除大模型提供商",
)
async def delete_provider(
    provider_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await LLMProviderService.delete_provider(session, provider_id)
    return success_response(DeleteResult(id=provider_id), msg="大模型提供商删除成功")


@router.post(
    "/providers/{provider_id}/set-default",
    response_model=ApiResponse[LLMProviderRead],
    summary="设置默认大模型提供商",
)
async def set_default_provider(
    provider_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[LLMProviderRead]:
    record = await LLMProviderService.set_default(session, provider_id)
    return success_response(
        LLMProviderRead.from_record(record),
        msg="默认大模型提供商设置成功",
    )


@router.post(
    "/models",
    response_model=ApiResponse[LLMModelListRead],
    summary="获取 OpenAI 兼容服务的模型列表",
)
async def list_remote_models(
    payload: LLMModelListRequest,
    session: SessionDep,
) -> ApiResponse[LLMModelListRead]:
    result = await LLMConnectionService.list_models(session, payload)
    return success_response(result, msg="模型列表获取成功")


@router.post(
    "/test",
    response_model=ApiResponse[LLMConnectionTestRead],
    summary="测试大模型连接和指定模型",
)
async def test_llm_connection(
    payload: LLMConnectionTestRequest,
    session: SessionDep,
) -> ApiResponse[LLMConnectionTestRead]:
    result = await LLMConnectionService.test_connection(session, payload)
    return success_response(result, msg="模型连接测试成功")


@router.get(
    "/current",
    response_model=ApiResponse[CurrentLLMConfigRead],
    summary="获取当前生效的大模型配置",
)
async def get_current_config(
    session: SessionDep,
) -> ApiResponse[CurrentLLMConfigRead]:
    config = await get_current_llm_config(session)
    data = CurrentLLMConfigRead(
        source=config.source,
        provider_id=config.provider_id,
        provider_name=config.provider_name,
        provider_type=config.provider_type,
        base_url=config.base_url,
        api_key=mask_api_key(config.api_key),
        default_model=config.default_model,
        timeout_seconds=config.timeout_seconds,
        extra_config=config.extra_config,
        is_configured=bool(config.api_key),
    )
    return success_response(data)
