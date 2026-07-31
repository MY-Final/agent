import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class LlmUsageStats(BaseModel):
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal("0")
    avg_latency_ms: float | None = None


class PurposeUsageStats(BaseModel):
    purpose: str
    calls: int = 0
    success_calls: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal("0")


class ModelUsageStats(BaseModel):
    model: str
    calls: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal("0")


class TaskCostStats(BaseModel):
    task_id: uuid.UUID
    task_name: str
    calls: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal("0")


class DailyUsageStats(BaseModel):
    date: date
    calls: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal("0")


class TaskFlowStats(BaseModel):
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    success_rate: float | None = None
    avg_duration_seconds: float | None = None


class StatsSummary(BaseModel):
    llm: LlmUsageStats
    tasks: TaskFlowStats
    by_purpose: list[PurposeUsageStats]
    by_model: list[ModelUsageStats]
    by_task: list[TaskCostStats]
    daily: list[DailyUsageStats]
