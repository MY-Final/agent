import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.agent_run import AgentRunStatus, AgentStep
from app.models.task import TaskStatus


class AgentConfirmInput(BaseModel):
    remark: str | None = Field(
        default=None,
        max_length=2000,
        description="人工确认备注，可为空",
    )


class AgentParseSummary(BaseModel):
    project_name: str | None = None
    project_code: str | None = None
    budget: str | None = None
    qualification_count: int = 0
    raw_summary: str | None = None


class AgentMatchSummary(BaseModel):
    overall_match_score: float | None = None
    summary: str
    matched_count: int = 0
    missing_count: int = 0
    risk_count: int = 0


class AgentStatusRead(BaseModel):
    run_id: uuid.UUID
    task_id: uuid.UUID
    thread_id: str
    current_step: AgentStep
    status: AgentRunStatus
    task_status: TaskStatus
    is_waiting_confirmation: bool
    user_confirmed: bool
    confirmation_note: str | None
    parse_result_id: uuid.UUID | None
    match_result_id: uuid.UUID | None
    parse_summary: AgentParseSummary | None
    match_summary: AgentMatchSummary | None
    error_message: str | None
    extra: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

