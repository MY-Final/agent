import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CertificateStatus(str, enum.Enum):
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"


class QualificationCertificate(Base):
    """公司持有的企业资质证书。"""

    __tablename__ = "qualification_certificates"
    __table_args__ = (
        Index("ix_qualification_certificates_name_level", "name", "level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cert_number: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(
            CertificateStatus,
            name="qualification_certificate_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=CertificateStatus.VALID,
        server_default=CertificateStatus.VALID.value,
        index=True,
    )
    file_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def is_currently_valid(self) -> bool:
        today = date.today()
        return (
            self.status == CertificateStatus.VALID
            and (self.valid_from is None or self.valid_from <= today)
            and (self.valid_to is None or self.valid_to >= today)
        )


class PerformanceRecord(Base):
    """公司历史项目业绩。"""

    __tablename__ = "performance_records"
    __table_args__ = (
        Index("ix_performance_records_amount_completed", "project_amount", "is_completed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True, index=True
    )
    currency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="CNY", server_default="CNY"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_qualification: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PersonnelCertificate(Base):
    """公司在职人员及其职业证书。"""

    __tablename__ = "personnel_certificates"
    __table_args__ = (
        Index("ix_personnel_certificates_type_specialty", "cert_type", "specialty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    person_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    cert_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cert_number: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_on_job: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    file_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def is_currently_valid(self) -> bool:
        today = date.today()
        return (
            self.is_on_job
            and (self.valid_from is None or self.valid_from <= today)
            and (self.valid_to is None or self.valid_to >= today)
        )


class CompanyProfile(Base):
    """公司基本信息，可保存多个投标主体。"""

    __tablename__ = "company_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, unique=True
    )
    legal_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registered_capital: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    establish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
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
