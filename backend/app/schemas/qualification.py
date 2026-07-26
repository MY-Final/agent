import math
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.qualification import CertificateStatus


ItemT = TypeVar("ItemT")


class PaginatedData(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[ItemT],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedData[ItemT]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )


class DateRangeMixin(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeMixin":
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("有效期开始日期不能晚于结束日期")
        return self


class QualificationCertificateCreate(DateRangeMixin):
    name: str = Field(min_length=1, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=255)
    cert_number: str | None = Field(default=None, max_length=255)
    issuing_authority: str | None = Field(default=None, max_length=255)
    status: CertificateStatus = CertificateStatus.VALID
    file_object_key: str | None = Field(default=None, max_length=1024)
    remark: str | None = None


class QualificationCertificateUpdate(DateRangeMixin):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=255)
    cert_number: str | None = Field(default=None, max_length=255)
    issuing_authority: str | None = Field(default=None, max_length=255)
    status: CertificateStatus | None = None
    file_object_key: str | None = Field(default=None, max_length=1024)
    remark: str | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "QualificationCertificateUpdate":
        for field, label in (("name", "证书名称"), ("status", "证书状态")):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{label}不能为 null")
        return self


class QualificationCertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    level: str | None
    specialty: str | None
    cert_number: str | None
    issuing_authority: str | None
    valid_from: date | None
    valid_to: date | None
    status: CertificateStatus
    is_currently_valid: bool
    file_object_key: str | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class PerformanceRecordCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    project_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", min_length=1, max_length=16)
    start_date: date | None = None
    end_date: date | None = None
    is_completed: bool = True
    owner_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    related_qualification: str | None = Field(default=None, max_length=500)
    description: str | None = None
    file_object_key: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def validate_date_range(self) -> "PerformanceRecordCreate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("项目开始日期不能晚于结束日期")
        return self


class PerformanceRecordUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=255)
    project_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=16)
    start_date: date | None = None
    end_date: date | None = None
    is_completed: bool | None = None
    owner_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    related_qualification: str | None = Field(default=None, max_length=500)
    description: str | None = None
    file_object_key: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def validate_date_range(self) -> "PerformanceRecordUpdate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("项目开始日期不能晚于结束日期")
        for field, label in (
            ("project_name", "项目名称"),
            ("currency", "币种"),
            ("is_completed", "完成状态"),
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{label}不能为 null")
        return self


class PerformanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_name: str
    project_amount: Decimal | None
    currency: str
    start_date: date | None
    end_date: date | None
    is_completed: bool
    owner_name: str | None
    location: str | None
    related_qualification: str | None
    description: str | None
    file_object_key: str | None
    created_at: datetime
    updated_at: datetime


class PersonnelCertificateCreate(DateRangeMixin):
    person_name: str = Field(min_length=1, max_length=100)
    cert_type: str = Field(min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    cert_number: str | None = Field(default=None, max_length=255)
    is_on_job: bool = True
    file_object_key: str | None = Field(default=None, max_length=1024)
    remark: str | None = None


class PersonnelCertificateUpdate(DateRangeMixin):
    person_name: str | None = Field(default=None, min_length=1, max_length=100)
    cert_type: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    cert_number: str | None = Field(default=None, max_length=255)
    is_on_job: bool | None = None
    file_object_key: str | None = Field(default=None, max_length=1024)
    remark: str | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "PersonnelCertificateUpdate":
        for field, label in (
            ("person_name", "人员姓名"),
            ("cert_type", "证书类型"),
            ("is_on_job", "在职状态"),
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{label}不能为 null")
        return self


class PersonnelCertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_name: str
    cert_type: str
    specialty: str | None
    cert_number: str | None
    valid_from: date | None
    valid_to: date | None
    is_on_job: bool
    is_currently_valid: bool
    file_object_key: str | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class CompanyProfileCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    legal_person: str | None = Field(default=None, max_length=100)
    registered_capital: Decimal | None = Field(default=None, ge=0)
    establish_date: date | None = None
    address: str | None = Field(default=None, max_length=500)
    contact_info: str | None = Field(default=None, max_length=500)
    extra_info: dict[str, Any] = Field(default_factory=dict)


class CompanyProfileUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_person: str | None = Field(default=None, max_length=100)
    registered_capital: Decimal | None = Field(default=None, ge=0)
    establish_date: date | None = None
    address: str | None = Field(default=None, max_length=500)
    contact_info: str | None = Field(default=None, max_length=500)
    extra_info: dict[str, Any] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "CompanyProfileUpdate":
        for field, label in (("company_name", "公司名称"), ("extra_info", "扩展信息")):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{label}不能为 null")
        return self


class CompanyProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    legal_person: str | None
    registered_capital: Decimal | None
    establish_date: date | None
    address: str | None
    contact_info: str | None
    extra_info: dict[str, Any]
    created_at: datetime
    updated_at: datetime


CertificateListData = PaginatedData[QualificationCertificateRead]
PerformanceListData = PaginatedData[PerformanceRecordRead]
PersonnelListData = PaginatedData[PersonnelCertificateRead]
CompanyListData = PaginatedData[CompanyProfileRead]
