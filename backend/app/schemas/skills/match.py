import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.match_result import MatchResultStatus, TaskMatchResult


class RiskLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    requirement: str
    company_status: str
    is_matched: bool
    risk_level: RiskLevel = RiskLevel.NONE
    comment: str | None = None


class MatchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_match_score: float | None = Field(default=None, ge=0, le=100)
    summary: str
    matched_items: list[MatchItem] = Field(default_factory=list)
    missing_items: list[MatchItem] = Field(default_factory=list)
    risk_items: list[MatchItem] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class MatchInput(BaseModel):
    """独立匹配入口，一次必须且只能选择一种解析结果定位方式。"""

    task_id: uuid.UUID | None = Field(
        default=None,
        description="使用该任务最新一次成功的标书解析结果",
    )
    parse_result_id: uuid.UUID | None = Field(
        default=None,
        description="使用指定的 task_parse_results 记录",
    )

    @model_validator(mode="after")
    def validate_single_source(self) -> "MatchInput":
        selected = sum(
            value is not None for value in (self.task_id, self.parse_result_id)
        )
        if selected != 1:
            raise ValueError("task_id、parse_result_id 必须且只能填写一个")
        return self


class MatchResultRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    parse_result_id: uuid.UUID | None
    status: MatchResultStatus
    result: MatchReport | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_record(cls, record: TaskMatchResult) -> "MatchResultRead":
        report = (
            MatchReport.model_validate(record.result_json)
            if record.result_json is not None
            else None
        )
        return cls(
            id=record.id,
            task_id=record.task_id,
            parse_result_id=record.parse_result_id,
            status=record.status,
            result=report,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
