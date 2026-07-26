import math
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, StorageException
from app.core.minio import MinIOStorage
from app.models.task import Task, TaskFile, TaskStatus
from app.schemas.task import TaskCreate, TaskListData, TaskListItem, TaskUpdate


class TaskService:
    @staticmethod
    async def create(session: AsyncSession, payload: TaskCreate) -> Task:
        task = Task(**payload.model_dump())
        session.add(task)
        await session.commit()
        return await TaskService.get(session, task.id)

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        *,
        status: TaskStatus | None,
        page: int,
        page_size: int,
    ) -> TaskListData:
        filters = [Task.status == status] if status is not None else []
        count_statement = select(func.count(Task.id)).where(*filters)
        total = int((await session.scalar(count_statement)) or 0)

        file_count = (
            select(func.count(TaskFile.id))
            .where(TaskFile.task_id == Task.id)
            .correlate(Task)
            .scalar_subquery()
        )
        statement = (
            select(Task, file_count.label("file_count"))
            .where(*filters)
            .order_by(Task.created_at.desc(), Task.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(statement)).all()
        items = [
            TaskListItem.model_validate(task).model_copy(
                update={"file_count": int(count or 0)}
            )
            for task, count in rows
        ]

        return TaskListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    @staticmethod
    async def get(session: AsyncSession, task_id: uuid.UUID) -> Task:
        statement = (
            select(Task).options(selectinload(Task.files)).where(Task.id == task_id)
        )
        task = await session.scalar(statement)
        if task is None:
            raise NotFoundException("任务不存在")
        return task

    @staticmethod
    async def ensure_exists(session: AsyncSession, task_id: uuid.UUID) -> None:
        statement = select(Task.id).where(Task.id == task_id)
        if await session.scalar(statement) is None:
            raise NotFoundException("任务不存在")

    @staticmethod
    async def update(
        session: AsyncSession,
        task_id: uuid.UUID,
        payload: TaskUpdate,
    ) -> Task:
        task = await TaskService.get(session, task_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        await session.commit()
        return await TaskService.get(session, task_id)

    @staticmethod
    async def update_status(
        session: AsyncSession,
        task_id: uuid.UUID,
        status: TaskStatus,
    ) -> Task:
        task = await TaskService.get(session, task_id)
        task.status = status
        await session.commit()
        return await TaskService.get(session, task_id)

    @staticmethod
    async def delete(
        session: AsyncSession,
        storage: MinIOStorage,
        task_id: uuid.UUID,
    ) -> None:
        await TaskService.ensure_exists(session, task_id)
        # 直接查询文件表，避免同一会话中 Task.files 已缓存为空时漏删对象。
        object_key_statement = select(TaskFile.object_key).where(
            TaskFile.task_id == task_id
        )
        object_keys = list((await session.scalars(object_key_statement)).all())

        # 先删除对象存储中的文件，失败时保留数据库记录，便于后续重试。
        try:
            await storage.delete_objects(object_keys)
        except Exception as exc:
            await session.rollback()
            raise StorageException("删除任务关联的 MinIO 文件失败") from exc

        await session.execute(delete(Task).where(Task.id == task_id))
        await session.commit()
