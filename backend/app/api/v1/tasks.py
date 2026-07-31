import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.models.task import TaskStatus
from app.schemas.task import (
    DeleteResult,
    TaskCreate,
    TaskListData,
    TaskRead,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.task_service import TaskService


router = APIRouter(prefix="/tasks", tags=["任务管理"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "",
    response_model=ApiResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建任务",
)
async def create_task(payload: TaskCreate, session: SessionDep) -> ApiResponse[TaskRead]:
    task = await TaskService.create(session, payload)
    return success_response(TaskRead.model_validate(task), msg="任务创建成功")


@router.get("", response_model=ApiResponse[TaskListData], summary="获取任务列表")
async def list_tasks(
    session: SessionDep,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[TaskListData]:
    result = await TaskService.list_tasks(
        session,
        status=task_status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success_response(result)


@router.get("/{task_id}", response_model=ApiResponse[TaskRead], summary="获取任务详情")
async def get_task(task_id: uuid.UUID, session: SessionDep) -> ApiResponse[TaskRead]:
    task = await TaskService.get(session, task_id)
    return success_response(TaskRead.model_validate(task))


@router.put("/{task_id}", response_model=ApiResponse[TaskRead], summary="更新任务信息")
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    session: SessionDep,
) -> ApiResponse[TaskRead]:
    task = await TaskService.update(session, task_id, payload)
    return success_response(TaskRead.model_validate(task), msg="任务更新成功")


@router.delete(
    "/{task_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除任务",
)
async def delete_task(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await TaskService.delete(session, minio_storage, task_id)
    return success_response(DeleteResult(id=task_id), msg="任务删除成功")


@router.patch(
    "/{task_id}/status",
    response_model=ApiResponse[TaskRead],
    summary="更新任务状态",
)
async def update_task_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    session: SessionDep,
) -> ApiResponse[TaskRead]:
    task = await TaskService.update_status(session, task_id, payload.status)
    return success_response(TaskRead.model_validate(task), msg="任务状态更新成功")
