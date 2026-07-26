import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentStep(str, enum.Enum):
    PARSE = "parse"
    WAIT_CONFIRM = "wait_confirm"
    MATCH = "match"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "running"
    WAITING_CONFIRM = "waiting_confirm"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Base):
    """单任务 Agent 的业务运行状态。

    LangGraph checkpoint 保存节点级恢复信息，本表保存前端查询需要的稳定业务状态。
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_task_created", "task_id", "created_at"),
        Index("ix_agent_runs_task_status", "task_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    current_step: Mapped[AgentStep] = mapped_column(
        Enum(
            AgentStep,
            name="agent_step",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=AgentStep.PARSE,
        server_default=AgentStep.PARSE.value,
        index=True,
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            name="agent_run_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=AgentRunStatus.RUNNING,
        server_default=AgentRunStatus.RUNNING.value,
        index=True,
    )
    parse_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_parse_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    match_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_match_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    task: Mapped["Task"] = relationship(back_populates="agent_runs")

