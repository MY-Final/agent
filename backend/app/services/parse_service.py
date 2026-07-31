import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFoundException, StorageException
from app.core.minio import MinIOStorage
from app.models.parse_result import ParseResultStatus, TaskParseResult
from app.models.task import Task, TaskFile, TaskStatus
from app.schemas.skills.parse import ParseInput, ParseTemplate
from app.services.template_service import TemplateService
from app.skills.parse_tender import ParseTenderSkill, TenderDocument
from app.skills.text_extractor import TextExtractor


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ParseSource:
    object_key: str
    filename: str
    task_id: uuid.UUID | None = None
    file_id: uuid.UUID | None = None


class ParseService:
    @staticmethod
    async def parse_from_input(
        session: AsyncSession,
        storage: MinIOStorage,
        payload: ParseInput,
    ) -> TaskParseResult:
        if payload.task_id is not None:
            return await ParseService.parse_task(session, storage, payload.task_id)

        source = await ParseService._resolve_single_source(session, payload)
        template, template_id = await TemplateService.resolve_parse_template(session)
        return await ParseService._execute(
            session=session,
            storage=storage,
            sources=[source],
            task_id=source.task_id,
            file_id=source.file_id,
            template=template,
            template_id=template_id,
            update_task_status=source.task_id is not None,
        )

    @staticmethod
    async def parse_task(
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
    ) -> TaskParseResult:
        task = await ParseService._get_task(session, task_id)
        template, template_id = await TemplateService.resolve_parse_template(
            session,
            task.parse_template_id,
        )
        statement = (
            select(TaskFile)
            .where(TaskFile.task_id == task_id)
            .order_by(TaskFile.uploaded_at.asc(), TaskFile.id.asc())
        )
        task_files = list((await session.scalars(statement)).all())
        sources = [
            ParseSource(
                object_key=task_file.object_key,
                filename=task_file.original_filename,
                task_id=task_id,
                file_id=task_file.id,
            )
            for task_file in task_files
            if TextExtractor.is_supported(task_file.original_filename)
        ]
        return await ParseService._execute(
            session=session,
            storage=storage,
            sources=sources,
            task_id=task_id,
            file_id=sources[0].file_id if len(sources) == 1 else None,
            template=template,
            template_id=template_id,
            update_task_status=True,
        )

    @staticmethod
    async def get_latest_result(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> TaskParseResult:
        await ParseService._get_task(session, task_id)
        statement = (
            select(TaskParseResult)
            .where(TaskParseResult.task_id == task_id)
            .order_by(TaskParseResult.created_at.desc(), TaskParseResult.id.desc())
            .limit(1)
        )
        record = await session.scalar(statement)
        if record is None:
            raise NotFoundException("该任务暂无解析结果")
        return record

    @staticmethod
    async def list_results(
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> list[TaskParseResult]:
        """按时间倒序返回任务的全部解析历史，支持多模板版本共存与追溯。"""

        await ParseService._get_task(session, task_id)
        statement = (
            select(TaskParseResult)
            .where(TaskParseResult.task_id == task_id)
            .order_by(TaskParseResult.created_at.desc(), TaskParseResult.id.desc())
        )
        return list((await session.scalars(statement)).all())

    @staticmethod
    async def _execute(
        *,
        session: AsyncSession,
        storage: MinIOStorage,
        sources: list[ParseSource],
        task_id: uuid.UUID | None,
        file_id: uuid.UUID | None,
        template: ParseTemplate,
        template_id: uuid.UUID | None,
        update_task_status: bool,
    ) -> TaskParseResult:
        source_keys = [source.object_key for source in sources]
        if update_task_status and task_id is not None:
            await ParseService._set_task_status(session, task_id, TaskStatus.PARSING)

        try:
            if not sources:
                raise ValueError("该任务下没有可解析的 PDF 或 DOCX 文件")
            with tempfile.TemporaryDirectory(prefix="tender_parse_") as temp_dir:
                documents = await ParseService._download_sources(
                    storage,
                    sources,
                    Path(temp_dir),
                )
                result = await ParseTenderSkill().run(documents, template=template)

            record = TaskParseResult(
                task_id=task_id,
                file_id=file_id,
                source_object_keys=source_keys,
                template_id=template_id,
                template_version=template.version,
                result_json=result.model_dump(mode="json"),
                status=ParseResultStatus.SUCCESS,
                error_message=None,
            )
            session.add(record)
            if update_task_status and task_id is not None:
                task = await ParseService._get_task(session, task_id)
                task.status = TaskStatus.WAITING_CONFIRM
            await session.commit()
            await session.refresh(record)
            return record
        except Exception as exc:
            if isinstance(exc, (AppException, ValueError)):
                logger.warning("标书解析失败，object_keys=%s：%s", source_keys, exc)
            else:
                logger.exception("标书解析失败，object_keys=%s", source_keys)
            await session.rollback()
            error_message = ParseService._error_message(exc)
            failure_record = TaskParseResult(
                task_id=task_id,
                file_id=file_id,
                source_object_keys=source_keys,
                template_id=template_id,
                template_version=template.version,
                result_json=None,
                status=ParseResultStatus.FAILED,
                error_message=error_message,
            )
            session.add(failure_record)
            if update_task_status and task_id is not None:
                task = await ParseService._get_task(session, task_id)
                task.status = TaskStatus.FAILED
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("保存标书解析失败记录时发生异常")

            if isinstance(exc, AppException):
                raise
            if isinstance(exc, ValueError):
                raise AppException(error_message, code=42201, status_code=422) from exc
            raise AppException(
                f"标书解析失败：{error_message}",
                code=50021,
                status_code=500,
            ) from exc

    @staticmethod
    async def _download_sources(
        storage: MinIOStorage,
        sources: list[ParseSource],
        temp_dir: Path,
    ) -> list[TenderDocument]:
        documents: list[TenderDocument] = []
        for index, source in enumerate(sources, start=1):
            suffix = Path(source.filename).suffix.lower()
            if suffix not in TextExtractor.SUPPORTED_SUFFIXES:
                raise ValueError("暂不支持该文件格式，目前仅支持 PDF 和 DOCX")

            local_path = temp_dir / f"{index:04d}_{uuid.uuid4().hex}{suffix}"
            try:
                await storage.download_to_path(source.object_key, local_path)
            except FileNotFoundError as exc:
                raise NotFoundException(
                    f"MinIO 中不存在文件对象：{source.object_key}"
                ) from exc
            except Exception as exc:
                raise StorageException(
                    f"从 MinIO 下载标书文件失败：{source.filename}"
                ) from exc

            documents.append(
                TenderDocument(
                    filename=source.filename,
                    object_key=source.object_key,
                    local_path=local_path,
                )
            )
        return documents

    @staticmethod
    async def _resolve_single_source(
        session: AsyncSession,
        payload: ParseInput,
    ) -> ParseSource:
        if payload.file_id is not None:
            statement = select(TaskFile).where(TaskFile.id == payload.file_id)
            task_file = await session.scalar(statement)
            if task_file is None:
                raise NotFoundException("任务文件不存在")
            return ParseSource(
                object_key=task_file.object_key,
                filename=task_file.original_filename,
                task_id=task_file.task_id,
                file_id=task_file.id,
            )

        object_key = payload.object_key or ""
        statement = select(TaskFile).where(TaskFile.object_key == object_key)
        task_file = await session.scalar(statement)
        if task_file is not None:
            return ParseSource(
                object_key=task_file.object_key,
                filename=task_file.original_filename,
                task_id=task_file.task_id,
                file_id=task_file.id,
            )

        filename = PurePath(object_key.replace("\\", "/")).name
        if not filename:
            raise AppException("object_key 中缺少文件名", code=40022, status_code=400)
        return ParseSource(object_key=object_key, filename=filename)

    @staticmethod
    async def _get_task(session: AsyncSession, task_id: uuid.UUID) -> Task:
        task = await session.scalar(select(Task).where(Task.id == task_id))
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    async def _set_task_status(
        session: AsyncSession,
        task_id: uuid.UUID,
        status: TaskStatus,
    ) -> None:
        task = await ParseService._get_task(session, task_id)
        task.status = status
        await session.commit()

    @staticmethod
    def _error_message(exc: Exception) -> str:
        if isinstance(exc, AppException):
            return exc.message
        message = str(exc).strip()
        return message[:4000] if message else "未知解析错误"
