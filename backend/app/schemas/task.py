import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    remark: str | None = None
    source: str | None = Field(default=None, max_length=255)
    parse_template_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=255)
    remark: str | None = None
    source: str | None = Field(default=None, max_length=255)
    parse_template_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def reject_null_project_name(self) -> "TaskUpdate":
        if "project_name" in self.model_fields_set and self.project_name is None:
            raise ValueError("项目名称不能为 null")
        return self


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    original_filename: str
    object_key: str
    file_size: int
    content_type: str
    uploaded_at: datetime


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_name: str
    remark: str | None
    source: str | None
    parse_template_id: uuid.UUID | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    files: list[TaskFileRead] = Field(default_factory=list)


class TaskListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_name: str
    remark: str | None
    source: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    file_count: int = 0


class TaskListData(BaseModel):
    items: list[TaskListItem]
    total: int
    page: int
    page_size: int
    pages: int


class DownloadUrlData(BaseModel):
    url: str
    expires_in: int
    filename: str


class DeleteResult(BaseModel):
    id: uuid.UUID
    deleted: bool = True


class HealthData(BaseModel):
    status: str
    postgres: str
    redis: str
    minio: str
