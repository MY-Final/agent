import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.qualification import ExpiryWarningItem


class DashboardTaskCounts(BaseModel):
    total: int = 0
    running: int = 0
    waiting_confirm: int = 0
    completed: int = 0
    failed: int = 0


class DashboardRecentTask(BaseModel):
    id: uuid.UUID
    project_name: str
    status: str
    created_at: datetime
    file_count: int = 0


class DashboardPendingTask(BaseModel):
    id: uuid.UUID
    project_name: str
    created_at: datetime


class DashboardSummary(BaseModel):
    task_counts: DashboardTaskCounts
    pending_confirm_tasks: list[DashboardPendingTask]
    warnings: list[ExpiryWarningItem]
    warning_expired: int = 0
    warning_expiring: int = 0
    recent_tasks: list[DashboardRecentTask]
