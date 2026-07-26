import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.parse_result import ParseResultStatus, TaskParseResult


class QualificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="资质、业绩、人员、财务或其他")
    description: str
    is_mandatory: bool = True
    original_text: str | None = None


class ParseResult(BaseModel):
    """大模型必须返回的标书结构化结果。"""

    model_config = ConfigDict(extra="forbid")

    project_name: str | None = None
    project_code: str | None = None
    budget: str | None = None
    duration: str | None = None
    location: str | None = None
    purchaser: str | None = None
    qualifications: list[QualificationItem] = Field(default_factory=list)
    scoring_method: dict[str, Any] = Field(default_factory=dict)
    disqualification_items: list[str] = Field(default_factory=list)
    key_dates: dict[str, Any] = Field(default_factory=dict)
    other_key_points: list[str] = Field(default_factory=list)
    raw_summary: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ParseInput(BaseModel):
    """独立 Skill 调试入口，一次必须且只能选择一种文件定位方式。"""

    task_id: uuid.UUID | None = Field(
        default=None,
        description="解析该任务下全部支持的标书文件",
    )
    file_id: uuid.UUID | None = Field(
        default=None,
        description="解析 task_files 中的单个文件",
    )
    object_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="直接解析 MinIO object_key，适合独立调试",
    )

    @model_validator(mode="after")
    def validate_single_source(self) -> "ParseInput":
        selected = sum(
            value is not None
            for value in (self.task_id, self.file_id, self.object_key)
        )
        if selected != 1:
            raise ValueError("task_id、file_id、object_key 必须且只能填写一个")
        return self


class ParseResultRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    file_id: uuid.UUID | None
    source_object_keys: list[str]
    status: ParseResultStatus
    result: ParseResult | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_record(cls, record: TaskParseResult) -> "ParseResultRead":
        parsed_result = (
            ParseResult.model_validate(record.result_json)
            if record.result_json is not None
            else None
        )
        return cls(
            id=record.id,
            task_id=record.task_id,
            file_id=record.file_id,
            source_object_keys=record.source_object_keys,
            status=record.status,
            result=parsed_result,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
