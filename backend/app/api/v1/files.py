import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.schemas.task import (
    DeleteResult,
    DownloadUrlData,
    TaskFileRead,
)
from app.services.file_service import FileService


router = APIRouter(prefix="/tasks/{task_id}/files", tags=["任务文件"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/upload",
    response_model=ApiResponse[TaskFileRead],
    status_code=status.HTTP_201_CREATED,
    summary="上传文件",
)
async def upload_file(
    task_id: uuid.UUID,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="需要上传的文件")],
) -> ApiResponse[TaskFileRead]:
    task_file = await FileService.upload_file(session, minio_storage, task_id, file)
    return success_response(TaskFileRead.model_validate(task_file), msg="文件上传成功")


@router.get("", response_model=ApiResponse[list[TaskFileRead]], summary="获取任务文件列表")
async def list_files(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[list[TaskFileRead]]:
    files = await FileService.list_files(session, task_id)
    return success_response([TaskFileRead.model_validate(item) for item in files])


@router.get(
    "/{file_id}/download",
    response_model=ApiResponse[DownloadUrlData],
    summary="获取文件下载地址",
)
async def get_download_url(
    task_id: uuid.UUID,
    file_id: uuid.UUID,
    session: SessionDep,
    expires_in: Annotated[int | None, Query(ge=1, le=604800)] = None,
) -> ApiResponse[DownloadUrlData]:
    result = await FileService.get_download_url(
        session,
        minio_storage,
        task_id,
        file_id,
        expires_in,
    )
    return success_response(result)


@router.delete(
    "/{file_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除任务文件",
)
async def delete_file(
    task_id: uuid.UUID,
    file_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await FileService.delete_file(session, minio_storage, task_id, file_id)
    return success_response(DeleteResult(id=file_id), msg="文件删除成功")
