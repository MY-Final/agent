from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskFile, TaskStatus
from app.schemas.dashboard import (
    DashboardPendingTask,
    DashboardRecentTask,
    DashboardSummary,
    DashboardTaskCounts,
)
from app.services.qualification_service import QualificationService


class DashboardService:
    @staticmethod
    async def get_summary(session: AsyncSession) -> DashboardSummary:
        rows = (
            await session.execute(
                select(Task.status, func.count()).group_by(Task.status)
            )
        ).all()
        counts = {status.value: int(count) for status, count in rows}
        task_counts = DashboardTaskCounts(
            total=sum(counts.values()),
            running=(
                counts.get(TaskStatus.PARSING.value, 0)
                + counts.get(TaskStatus.ANALYZING.value, 0)
                + counts.get(TaskStatus.GENERATING.value, 0)
            ),
            waiting_confirm=counts.get(TaskStatus.WAITING_CONFIRM.value, 0),
            completed=counts.get(TaskStatus.COMPLETED.value, 0),
            failed=counts.get(TaskStatus.FAILED.value, 0),
        )

        warnings_data = await QualificationService.get_expiry_warnings(session)

        pending_rows = list(
            (
                await session.scalars(
                    select(Task)
                    .where(Task.status == TaskStatus.WAITING_CONFIRM)
                    .order_by(Task.updated_at.desc(), Task.id.desc())
                    .limit(5)
                )
            ).all()
        )
        pending_tasks = [
            DashboardPendingTask(
                id=task.id,
                project_name=task.project_name,
                created_at=task.created_at,
            )
            for task in pending_rows
        ]

        file_count = (
            select(func.count(TaskFile.id))
            .where(TaskFile.task_id == Task.id)
            .correlate(Task)
            .scalar_subquery()
        )
        recent_statement = (
            select(Task, file_count.label("file_count"))
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(6)
        )
        recent_tasks = [
            DashboardRecentTask(
                id=task.id,
                project_name=task.project_name,
                status=task.status.value,
                created_at=task.created_at,
                file_count=int(count or 0),
            )
            for task, count in (await session.execute(recent_statement)).all()
        ]

        return DashboardSummary(
            task_counts=task_counts,
            pending_confirm_tasks=pending_tasks,
            warnings=warnings_data.items,
            warning_expired=warnings_data.expired_count,
            warning_expiring=warnings_data.expiring_count,
            recent_tasks=recent_tasks,
        )
