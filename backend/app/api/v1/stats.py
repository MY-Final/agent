from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.response import ApiResponse, success_response
from app.schemas.stats import StatsSummary
from app.services.stats_service import StatsService


router = APIRouter(prefix="/stats", tags=["统计与成本"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/summary",
    response_model=ApiResponse[StatsSummary],
    summary="获取 LLM 用量成本与任务流程统计",
)
async def stats_summary(
    session: SessionDep,
) -> ApiResponse[StatsSummary]:
    return success_response(await StatsService.get_summary(session))
