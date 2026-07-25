import logging
import mimetypes
import uuid
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, NotFoundException, StorageException
from app.core.minio import MinIOStorage
from app.models.task import TaskFile
from app.schemas.task import DownloadUrlData
from app.services.task_service import TaskService
from app.utils.file_utils import build_object_key, extract_original_filename


logger = logging.getLogger(__name__)


class FileService:
    @staticmethod
    async def upload_file(
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
        upload: UploadFile,
    ) -> TaskFile:
        await TaskService.ensure_exists(session, task_id)
        original_filename = extract_original_filename(upload.filename or "未命名文件")
        content_type = FileService._resolve_content_type(
            upload.content_type,
            original_filename,
        )

        try:
            file_size = upload.size
            if file_size is None:
                file_size = await FileService._get_upload_size(upload)
            FileService._validate_file_size(file_size)
            await upload.seek(0)
            return await FileService._store_file(
                session=session,
                storage=storage,
                task_id=task_id,
                fileobj=upload.file,
                original_filename=original_filename,
                content_type=content_type,
                file_size=file_size,
            )
        finally:
            await upload.close()

    @staticmethod
    async def list_files(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> list[TaskFile]:
        await TaskService.ensure_exists(session, task_id)
        statement = (
            select(TaskFile)
            .where(TaskFile.task_id == task_id)
            .order_by(TaskFile.uploaded_at.asc(), TaskFile.id.asc())
        )
        return list((await session.scalars(statement)).all())

    @staticmethod
    async def get_file(
        session: AsyncSession,
        task_id: uuid.UUID,
        file_id: uuid.UUID,
    ) -> TaskFile:
        statement = select(TaskFile).where(
            TaskFile.id == file_id,
            TaskFile.task_id == task_id,
        )
        task_file = await session.scalar(statement)
        if task_file is None:
            raise NotFoundException("任务文件不存在")
        return task_file

    @staticmethod
    async def get_download_url(
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
        file_id: uuid.UUID,
        expires_in: int | None,
    ) -> DownloadUrlData:
        task_file = await FileService.get_file(session, task_id, file_id)
        try:
            url, expiry = await storage.generate_presigned_download_url(
                task_file.object_key,
                task_file.original_filename,
                expires_in,
            )
        except Exception as exc:
            raise StorageException("生成 MinIO 文件下载地址失败") from exc

        return DownloadUrlData(
            url=url,
            expires_in=expiry,
            filename=task_file.original_filename,
        )

    @staticmethod
    async def delete_file(
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
        file_id: uuid.UUID,
    ) -> None:
        task_file = await FileService.get_file(session, task_id, file_id)
        try:
            await storage.delete_object(task_file.object_key)
        except Exception as exc:
            await session.rollback()
            raise StorageException("从 MinIO 删除文件失败") from exc

        await session.delete(task_file)
        await session.commit()

    @staticmethod
    async def _store_file(
        *,
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
        fileobj: BinaryIO,
        original_filename: str,
        content_type: str,
        file_size: int,
    ) -> TaskFile:
        FileService._validate_file_size(file_size)
        object_key = build_object_key(task_id, original_filename)

        # 主流程：先上传并确认 MinIO 对象有效，再写入数据库文件记录。
        try:
            await storage.upload_fileobj(
                fileobj,
                object_key,
                content_type,
                file_size,
            )
        except Exception as exc:
            raise StorageException("上传文件到 MinIO 失败") from exc

        task_file = TaskFile(
            task_id=task_id,
            original_filename=original_filename,
            object_key=object_key,
            file_size=file_size,
            content_type=content_type,
        )
        session.add(task_file)
        try:
            await session.commit()
            await session.refresh(task_file)
            return task_file
        except Exception as database_exc:
            await session.rollback()
            # 数据库写入失败时回收已经上传的对象，防止产生孤立文件。
            try:
                await storage.delete_object(object_key)
            except Exception as cleanup_exc:
                logger.exception("清理已上传的 MinIO 对象失败：%s", object_key)
                raise AppException(
                    "文件数据库记录保存失败，且 MinIO 补偿清理失败，请联系管理员",
                    code=50002,
                    status_code=500,
                ) from cleanup_exc
            raise AppException(
                "文件数据库记录保存失败，已回滚并清理 MinIO 对象",
                code=50001,
                status_code=500,
            ) from database_exc

    @staticmethod
    async def _get_upload_size(upload: UploadFile) -> int:
        await upload.seek(0)
        upload.file.seek(0, 2)
        size = upload.file.tell()
        await upload.seek(0)
        return size

    @staticmethod
    def _validate_file_size(file_size: int) -> None:
        if file_size <= 0:
            raise AppException("文件不能为空", code=40001, status_code=400)
        if file_size > settings.max_upload_size_bytes:
            raise AppException(
                f"文件大小超过限制，最大允许 {settings.max_upload_size_bytes} 字节",
                code=41300,
                status_code=413,
            )

    @staticmethod
    def _resolve_content_type(content_type: str | None, filename: str) -> str:
        """优先采用客户端 MIME 类型，无效或缺失时根据文件名推断。"""
        candidate = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
        if candidate and "/" in candidate and len(candidate) <= 255:
            return candidate
        guessed_type, _ = mimetypes.guess_type(filename)
        return guessed_type or "application/octet-stream"
