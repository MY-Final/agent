import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.schemas.skills.match import MatchInput, MatchResultRead
from app.schemas.skills.parse import ParseInput, ParseResultRead
from app.services.match_service import MatchService
from app.services.parse_service import ParseService


router = APIRouter(tags=["业务 Skills"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/skills/parse",
    response_model=ApiResponse[ParseResultRead],
    summary="独立调用标书解析 Skill",
)
async def parse_skill(
    payload: ParseInput,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.parse_from_input(session, minio_storage, payload)
    return success_response(
        ParseResultRead.from_orm_record(record),
        msg="标书解析成功",
    )


@router.post(
    "/tasks/{task_id}/parse",
    response_model=ApiResponse[ParseResultRead],
    summary="解析任务下的标书文件",
)
async def parse_task(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.parse_task(session, minio_storage, task_id)
    return success_response(
        ParseResultRead.from_orm_record(record),
        msg="任务标书解析成功",
    )


@router.get(
    "/tasks/{task_id}/parse-result",
    response_model=ApiResponse[ParseResultRead],
    summary="获取任务最新解析结果",
)
async def get_parse_result(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.get_latest_result(session, task_id)
    return success_response(ParseResultRead.from_orm_record(record))


@router.post(
    "/skills/match",
    response_model=ApiResponse[MatchResultRead],
    summary="独立调用资质匹配 Skill",
)
async def match_skill(
    payload: MatchInput,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.match_from_input(session, payload)
    return success_response(
        MatchResultRead.from_orm_record(record),
        msg="资质匹配成功",
    )


@router.post(
    "/tasks/{task_id}/match",
    response_model=ApiResponse[MatchResultRead],
    summary="匹配任务资格要求",
)
async def match_task(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.match_task(session, task_id)
    return success_response(
        MatchResultRead.from_orm_record(record),
        msg="任务资质匹配成功",
    )


@router.get(
    "/tasks/{task_id}/match-result",
    response_model=ApiResponse[MatchResultRead],
    summary="获取任务最新资质匹配结果",
)
async def get_match_result(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.get_latest_result(session, task_id)
    return success_response(MatchResultRead.from_orm_record(record))
