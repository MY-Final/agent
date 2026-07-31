import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import AppException
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.schemas.task import (
    DeleteResult,
    DownloadUrlData,
    PdfInfo,
    TaskFileRead,
)
from app.services.file_service import FileService
from app.services.pdf_render_service import PdfRenderService


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


@router.get(
    "/{file_id}/pdf-info",
    response_model=ApiResponse[PdfInfo],
    summary="获取 PDF 页数信息（原文预览用）",
)
async def get_pdf_info(
    task_id: uuid.UUID,
    file_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[PdfInfo]:
    task_file = await FileService.get_file(session, task_id, file_id)
    if not task_file.original_filename.lower().endswith(".pdf"):
        raise AppException(
            "该文件不是 PDF，无法页面预览",
            code=40024,
            status_code=400,
        )
    total_pages = await PdfRenderService.page_count(
        minio_storage,
        task_file.object_key,
    )
    return success_response(
        PdfInfo(
            filename=task_file.original_filename,
            total_pages=total_pages,
            content_type=task_file.content_type,
        )
    )


@router.get(
    "/{file_id}/pages/{page_number}",
    summary="渲染 PDF 指定页为 PNG",
)
async def render_pdf_page(
    task_id: uuid.UUID,
    file_id: uuid.UUID,
    page_number: int,
    session: SessionDep,
) -> StreamingResponse:
    task_file = await FileService.get_file(session, task_id, file_id)
    if not task_file.original_filename.lower().endswith(".pdf"):
        raise AppException(
            "该文件不是 PDF，无法页面预览",
            code=40024,
            status_code=400,
        )
    png = await PdfRenderService.render_page(
        minio_storage,
        task_file.object_key,
        page_number,
    )
    return StreamingResponse(
        io.BytesIO(png),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


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
