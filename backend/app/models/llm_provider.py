import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMProvider(Base):
    """可动态切换的 OpenAI 兼容大模型提供商配置。"""

    __tablename__ = "llm_providers"
    __table_args__ = (
        # PostgreSQL 部分唯一索引从数据库层保证全局最多一个默认提供商。
        Index(
            "uq_llm_providers_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        CheckConstraint(
            "timeout_seconds > 0 AND timeout_seconds <= 600",
            name="ck_llm_providers_timeout_seconds",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="openai_compatible",
        server_default="openai_compatible",
    )
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    default_model: Mapped[str] = mapped_column(String(255), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    extra_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
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
