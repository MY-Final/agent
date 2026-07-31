from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.response import ApiResponse, success_response
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["工作台"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/summary",
    response_model=ApiResponse[DashboardSummary],
    summary="获取工作台汇总",
)
async def dashboard_summary(
    session: SessionDep,
) -> ApiResponse[DashboardSummary]:
    return success_response(await DashboardService.get_summary(session))
