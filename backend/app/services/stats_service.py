from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.llm_usage import LLMUsage, LLMUsageStatus
from app.models.task import Task
from app.schemas.stats import (
    DailyUsageStats,
    LlmUsageStats,
    ModelUsageStats,
    PurposeUsageStats,
    StatsSummary,
    TaskCostStats,
    TaskFlowStats,
)


_ZERO = Decimal("0")


class StatsService:
    @staticmethod
    async def get_summary(session: AsyncSession) -> StatsSummary:
        llm = await StatsService._llm_stats(session)
        by_purpose = await StatsService._group_by_purpose(session)
        by_model = await StatsService._group_by_model(session)
        by_task = await StatsService._group_by_task(session)
        daily = await StatsService._daily_usage(session)
        tasks = await StatsService._task_flow(session)
        return StatsSummary(
            llm=llm,
            tasks=tasks,
            by_purpose=by_purpose,
            by_model=by_model,
            by_task=by_task,
            daily=daily,
        )

    @staticmethod
    async def _llm_stats(session: AsyncSession) -> LlmUsageStats:
        row = (
            await session.execute(
                select(
                    func.count(LLMUsage.id),
                    func.sum(
                        case(
                            (LLMUsage.status == LLMUsageStatus.SUCCESS, 1),
                            else_=0,
                        )
                    ),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0),
                    func.avg(LLMUsage.latency_ms),
                )
            )
        ).one()
        total_calls = int(row[0] or 0)
        success_calls = int(row[1] or 0)
        avg_latency = float(row[4]) if row[4] is not None else None
        return LlmUsageStats(
            total_calls=total_calls,
            success_calls=success_calls,
            failed_calls=total_calls - success_calls,
            total_tokens=int(row[2] or 0),
            total_cost=Decimal(row[3] or 0),
            avg_latency_ms=round(avg_latency, 1) if avg_latency is not None else None,
        )

    @staticmethod
    async def _group_by_purpose(session: AsyncSession) -> list[PurposeUsageStats]:
        rows = (
            await session.execute(
                select(
                    LLMUsage.purpose,
                    func.count(LLMUsage.id),
                    func.sum(
                        case(
                            (LLMUsage.status == LLMUsageStatus.SUCCESS, 1),
                            else_=0,
                        )
                    ),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0),
                )
                .group_by(LLMUsage.purpose)
                .order_by(LLMUsage.purpose)
            )
        ).all()
        return [
            PurposeUsageStats(
                purpose=str(row[0]),
                calls=int(row[1] or 0),
                success_calls=int(row[2] or 0),
                total_tokens=int(row[3] or 0),
                total_cost=Decimal(row[4] or 0),
            )
            for row in rows
        ]

    @staticmethod
    async def _group_by_model(session: AsyncSession) -> list[ModelUsageStats]:
        rows = (
            await session.execute(
                select(
                    LLMUsage.model,
                    func.count(LLMUsage.id),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0),
                )
                .group_by(LLMUsage.model)
                .order_by(
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0).desc()
                )
            )
        ).all()
        return [
            ModelUsageStats(
                model=str(row[0]),
                calls=int(row[1] or 0),
                total_tokens=int(row[2] or 0),
                total_cost=Decimal(row[3] or 0),
            )
            for row in rows
        ]

    @staticmethod
    async def _group_by_task(session: AsyncSession) -> list[TaskCostStats]:
        rows = (
            await session.execute(
                select(
                    LLMUsage.task_id,
                    Task.project_name,
                    func.count(LLMUsage.id),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0),
                )
                .join(Task, LLMUsage.task_id == Task.id)
                .where(LLMUsage.task_id.is_not(None))
                .group_by(LLMUsage.task_id, Task.project_name)
                .order_by(
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0).desc()
                )
                .limit(8)
            )
        ).all()
        return [
            TaskCostStats(
                task_id=row[0],
                task_name=str(row[1]),
                calls=int(row[2] or 0),
                total_tokens=int(row[3] or 0),
                total_cost=Decimal(row[4] or 0),
            )
            for row in rows
        ]

    @staticmethod
    async def _daily_usage(session: AsyncSession) -> list[DailyUsageStats]:
        today = date.today()
        start = today - timedelta(days=13)
        day_column = func.date(LLMUsage.created_at)
        rows = (
            await session.execute(
                select(
                    day_column.label("day"),
                    func.count(LLMUsage.id),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsage.estimated_cost), 0),
                )
                .where(day_column >= start)
                .group_by(day_column)
                .order_by(day_column)
            )
        ).all()
        by_day = {row[0]: row for row in rows}
        daily: list[DailyUsageStats] = []
        cursor = start
        while cursor <= today:
            row = by_day.get(cursor)
            daily.append(
                DailyUsageStats(
                    date=cursor,
                    calls=int(row[1] or 0) if row else 0,
                    total_tokens=int(row[2] or 0) if row else 0,
                    total_cost=Decimal(row[3] or 0) if row else _ZERO,
                )
            )
            cursor += timedelta(days=1)
        return daily

    @staticmethod
    async def _task_flow(session: AsyncSession) -> TaskFlowStats:
        status_rows = (
            await session.execute(
                select(AgentRun.status, func.count()).group_by(AgentRun.status)
            )
        ).all()
        counts = {status.value: int(count) for status, count in status_rows}
        completed = counts.get(AgentRunStatus.COMPLETED.value, 0)
        failed = counts.get(AgentRunStatus.FAILED.value, 0)
        total_runs = sum(counts.values())
        success_rate = (
            round(completed / (completed + failed) * 100, 1)
            if completed + failed
            else None
        )
        duration_rows = (
            await session.execute(
                select(AgentRun.started_at, AgentRun.completed_at).where(
                    AgentRun.status == AgentRunStatus.COMPLETED
                )
            )
        ).all()
        durations = [
            (completed_at - started_at).total_seconds()
            for started_at, completed_at in duration_rows
            if started_at is not None
            and completed_at is not None
            and completed_at > started_at
        ]
        avg_duration = (
            round(sum(durations) / len(durations), 1) if durations else None
        )
        return TaskFlowStats(
            total_runs=total_runs,
            completed_runs=completed,
            failed_runs=failed,
            success_rate=success_rate,
            avg_duration_seconds=avg_duration,
        )
