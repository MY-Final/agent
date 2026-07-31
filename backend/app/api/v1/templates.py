import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.response import ApiResponse, success_response
from app.schemas.parse_template import (
    ParseTemplateCreate,
    ParseTemplateRead,
    ParseTemplateUpdate,
    TemplateSuggestion,
    TemplateSuggestionInput,
)
from app.schemas.task import DeleteResult
from app.services.suggestion_service import TemplateSuggestionService
from app.services.template_service import TemplateService


router = APIRouter(prefix="/templates", tags=["解析模板"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "",
    response_model=ApiResponse[list[ParseTemplateRead]],
    summary="获取解析模板列表",
)
async def list_templates(
    session: SessionDep,
) -> ApiResponse[list[ParseTemplateRead]]:
    items = await TemplateService.list_templates(session)
    return success_response(items)


@router.post(
    "",
    response_model=ApiResponse[ParseTemplateRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建解析模板",
)
async def create_template(
    payload: ParseTemplateCreate,
    session: SessionDep,
) -> ApiResponse[ParseTemplateRead]:
    record = await TemplateService.create(session, payload)
    return success_response(
        ParseTemplateRead.from_record(record),
        msg="解析模板创建成功",
    )


@router.post(
    "/suggest",
    response_model=ApiResponse[TemplateSuggestion],
    summary="根据自然语言描述生成解析模板建议",
)
async def suggest_template(
    payload: TemplateSuggestionInput,
    session: SessionDep,
) -> ApiResponse[TemplateSuggestion]:
    suggestion = await TemplateSuggestionService.suggest(
        payload.description,
        payload.reference_text,
    )
    return success_response(suggestion, msg="模板建议生成成功")


@router.get(
    "/{template_id}",
    response_model=ApiResponse[ParseTemplateRead],
    summary="获取解析模板详情",
)
async def get_template(
    template_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[ParseTemplateRead]:
    record = await TemplateService.get(session, template_id)
    return success_response(ParseTemplateRead.from_record(record))


@router.put(
    "/{template_id}",
    response_model=ApiResponse[ParseTemplateRead],
    summary="更新解析模板",
)
async def update_template(
    template_id: uuid.UUID,
    payload: ParseTemplateUpdate,
    session: SessionDep,
) -> ApiResponse[ParseTemplateRead]:
    record = await TemplateService.update(session, template_id, payload)
    return success_response(
        ParseTemplateRead.from_record(record),
        msg="解析模板更新成功",
    )


@router.delete(
    "/{template_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除解析模板",
)
async def delete_template(
    template_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await TemplateService.delete(session, template_id)
    return success_response(
        DeleteResult(id=template_id),
        msg="解析模板删除成功",
    )
