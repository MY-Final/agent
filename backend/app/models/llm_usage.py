import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMUsageStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class LLMUsage(Base):
    """每一次大模型调用的用量与成本快照。

    所有 AI 调用都收口在 TenderLLMClient，因此这里能覆盖全部用到 AI 的场景。
    """

    __tablename__ = "llm_usages"
    __table_args__ = (
        Index("ix_llm_usages_created", "created_at"),
        Index("ix_llm_usages_purpose_created", "purpose", "created_at"),
        Index("ix_llm_usages_task_created", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    input_price_per_million: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    output_price_per_million: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[LLMUsageStatus] = mapped_column(
        Enum(
            LLMUsageStatus,
            name="llm_usage_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=LLMUsageStatus.SUCCESS,
        server_default=LLMUsageStatus.SUCCESS.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
