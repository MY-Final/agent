import uuid
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    ConflictException,
    NotFoundException,
    StorageException,
)
from app.core.minio import MinIOStorage
from app.models.qualification import (
    CertificateStatus,
    CompanyProfile,
    PerformanceRecord,
    PersonnelCertificate,
    QualificationCertificate,
)
from app.schemas.qualification import (
    CompanyProfileCreate,
    CompanyProfileUpdate,
    PerformanceRecordCreate,
    PerformanceRecordUpdate,
    PersonnelCertificateCreate,
    PersonnelCertificateUpdate,
    QualificationCertificateCreate,
    QualificationCertificateUpdate,
)


ModelT = TypeVar("ModelT")


class QualificationService:
    @staticmethod
    async def create_certificate(
        session: AsyncSession,
        payload: QualificationCertificateCreate,
    ) -> QualificationCertificate:
        record = QualificationCertificate(**payload.model_dump())
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def list_certificates(
        session: AsyncSession,
        *,
        name: str | None,
        status: CertificateStatus | None,
        is_valid: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[QualificationCertificate], int]:
        filters: list[Any] = []
        if name:
            filters.append(QualificationCertificate.name.ilike(f"%{name.strip()}%"))
        if status is not None:
            filters.append(QualificationCertificate.status == status)
        if is_valid is not None:
            valid_condition = QualificationService._certificate_valid_condition()
            filters.append(valid_condition if is_valid else not_(valid_condition))
        return await QualificationService._paginate(
            session,
            QualificationCertificate,
            filters,
            page,
            page_size,
            QualificationCertificate.created_at.desc(),
        )

    @staticmethod
    async def get_certificate(
        session: AsyncSession,
        record_id: uuid.UUID,
    ) -> QualificationCertificate:
        record = await session.get(QualificationCertificate, record_id)
        if record is None:
            raise NotFoundException("资质证书不存在")
        return record

    @staticmethod
    async def update_certificate(
        session: AsyncSession,
        record_id: uuid.UUID,
        payload: QualificationCertificateUpdate,
    ) -> QualificationCertificate:
        record = await QualificationService.get_certificate(session, record_id)
        values = payload.model_dump(exclude_unset=True)
        QualificationService._validate_merged_date_range(record, values, "有效期")
        QualificationService._apply_values(record, values)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def delete_certificate(
        session: AsyncSession,
        storage: MinIOStorage,
        record_id: uuid.UUID,
    ) -> None:
        record = await QualificationService.get_certificate(session, record_id)
        await QualificationService._delete_with_attachment(session, storage, record)

    @staticmethod
    async def create_performance(
        session: AsyncSession,
        payload: PerformanceRecordCreate,
    ) -> PerformanceRecord:
        record = PerformanceRecord(**payload.model_dump())
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def list_performances(
        session: AsyncSession,
        *,
        keyword: str | None,
        min_amount: Decimal | None,
        max_amount: Decimal | None,
        is_completed: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PerformanceRecord], int]:
        if min_amount is not None and max_amount is not None and min_amount > max_amount:
            raise AppException(
                "最小业绩金额不能大于最大业绩金额",
                code=42222,
                status_code=422,
            )
        filters: list[Any] = []
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    PerformanceRecord.project_name.ilike(pattern),
                    PerformanceRecord.owner_name.ilike(pattern),
                    PerformanceRecord.related_qualification.ilike(pattern),
                    PerformanceRecord.description.ilike(pattern),
                )
            )
        if min_amount is not None:
            filters.append(PerformanceRecord.project_amount >= min_amount)
        if max_amount is not None:
            filters.append(PerformanceRecord.project_amount <= max_amount)
        if is_completed is not None:
            filters.append(PerformanceRecord.is_completed == is_completed)
        return await QualificationService._paginate(
            session,
            PerformanceRecord,
            filters,
            page,
            page_size,
            PerformanceRecord.created_at.desc(),
        )

    @staticmethod
    async def get_performance(
        session: AsyncSession,
        record_id: uuid.UUID,
    ) -> PerformanceRecord:
        record = await session.get(PerformanceRecord, record_id)
        if record is None:
            raise NotFoundException("业绩记录不存在")
        return record

    @staticmethod
    async def update_performance(
        session: AsyncSession,
        record_id: uuid.UUID,
        payload: PerformanceRecordUpdate,
    ) -> PerformanceRecord:
        record = await QualificationService.get_performance(session, record_id)
        values = payload.model_dump(exclude_unset=True)
        QualificationService._validate_merged_date_range(
            record,
            values,
            "项目日期",
            start_field="start_date",
            end_field="end_date",
        )
        QualificationService._apply_values(record, values)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def delete_performance(
        session: AsyncSession,
        storage: MinIOStorage,
        record_id: uuid.UUID,
    ) -> None:
        record = await QualificationService.get_performance(session, record_id)
        await QualificationService._delete_with_attachment(session, storage, record)

    @staticmethod
    async def create_personnel(
        session: AsyncSession,
        payload: PersonnelCertificateCreate,
    ) -> PersonnelCertificate:
        record = PersonnelCertificate(**payload.model_dump())
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def list_personnel(
        session: AsyncSession,
        *,
        person_name: str | None,
        cert_type: str | None,
        specialty: str | None,
        is_on_job: bool | None,
        is_valid: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PersonnelCertificate], int]:
        filters: list[Any] = []
        if person_name:
            filters.append(
                PersonnelCertificate.person_name.ilike(f"%{person_name.strip()}%")
            )
        if cert_type:
            filters.append(
                PersonnelCertificate.cert_type.ilike(f"%{cert_type.strip()}%")
            )
        if specialty:
            filters.append(
                PersonnelCertificate.specialty.ilike(f"%{specialty.strip()}%")
            )
        if is_on_job is not None:
            filters.append(PersonnelCertificate.is_on_job == is_on_job)
        if is_valid is not None:
            valid_condition = QualificationService._personnel_valid_condition()
            filters.append(valid_condition if is_valid else not_(valid_condition))
        return await QualificationService._paginate(
            session,
            PersonnelCertificate,
            filters,
            page,
            page_size,
            PersonnelCertificate.created_at.desc(),
        )

    @staticmethod
    async def get_personnel(
        session: AsyncSession,
        record_id: uuid.UUID,
    ) -> PersonnelCertificate:
        record = await session.get(PersonnelCertificate, record_id)
        if record is None:
            raise NotFoundException("人员证书不存在")
        return record

    @staticmethod
    async def update_personnel(
        session: AsyncSession,
        record_id: uuid.UUID,
        payload: PersonnelCertificateUpdate,
    ) -> PersonnelCertificate:
        record = await QualificationService.get_personnel(session, record_id)
        values = payload.model_dump(exclude_unset=True)
        QualificationService._validate_merged_date_range(record, values, "有效期")
        QualificationService._apply_values(record, values)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def delete_personnel(
        session: AsyncSession,
        storage: MinIOStorage,
        record_id: uuid.UUID,
    ) -> None:
        record = await QualificationService.get_personnel(session, record_id)
        await QualificationService._delete_with_attachment(session, storage, record)

    @staticmethod
    async def create_company(
        session: AsyncSession,
        payload: CompanyProfileCreate,
    ) -> CompanyProfile:
        record = CompanyProfile(**payload.model_dump())
        session.add(record)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ConflictException("公司名称已存在") from exc
        await session.refresh(record)
        return record

    @staticmethod
    async def list_companies(
        session: AsyncSession,
        *,
        company_name: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CompanyProfile], int]:
        filters: list[Any] = []
        if company_name:
            filters.append(CompanyProfile.company_name.ilike(f"%{company_name.strip()}%"))
        return await QualificationService._paginate(
            session,
            CompanyProfile,
            filters,
            page,
            page_size,
            CompanyProfile.created_at.desc(),
        )

    @staticmethod
    async def get_company(
        session: AsyncSession,
        record_id: uuid.UUID,
    ) -> CompanyProfile:
        record = await session.get(CompanyProfile, record_id)
        if record is None:
            raise NotFoundException("公司信息不存在")
        return record

    @staticmethod
    async def update_company(
        session: AsyncSession,
        record_id: uuid.UUID,
        payload: CompanyProfileUpdate,
    ) -> CompanyProfile:
        record = await QualificationService.get_company(session, record_id)
        QualificationService._apply_values(record, payload.model_dump(exclude_unset=True))
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ConflictException("公司名称已存在") from exc
        await session.refresh(record)
        return record

    @staticmethod
    async def delete_company(session: AsyncSession, record_id: uuid.UUID) -> None:
        record = await QualificationService.get_company(session, record_id)
        await session.delete(record)
        await session.commit()

    @staticmethod
    async def get_knowledge_base(
        session: AsyncSession,
    ) -> tuple[
        list[QualificationCertificate],
        list[PerformanceRecord],
        list[PersonnelCertificate],
        list[CompanyProfile],
    ]:
        certificates = list(
            (await session.scalars(select(QualificationCertificate))).all()
        )
        performances = list((await session.scalars(select(PerformanceRecord))).all())
        personnel = list(
            (await session.scalars(select(PersonnelCertificate))).all()
        )
        companies = list((await session.scalars(select(CompanyProfile))).all())
        return certificates, performances, personnel, companies

    @staticmethod
    async def _paginate(
        session: AsyncSession,
        model: type[ModelT],
        filters: list[Any],
        page: int,
        page_size: int,
        order_by: Any,
    ) -> tuple[list[ModelT], int]:
        total = int(
            (await session.scalar(select(func.count()).select_from(model).where(*filters)))
            or 0
        )
        statement = (
            select(model)
            .where(*filters)
            .order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await session.scalars(statement)).all()), total

    @staticmethod
    async def _delete_with_attachment(
        session: AsyncSession,
        storage: MinIOStorage,
        record: QualificationCertificate | PerformanceRecord | PersonnelCertificate,
    ) -> None:
        if record.file_object_key:
            try:
                await storage.delete_object(record.file_object_key)
            except Exception as exc:
                await session.rollback()
                raise StorageException("删除资质关联的 MinIO 文件失败") from exc
        await session.delete(record)
        await session.commit()

    @staticmethod
    def _apply_values(record: Any, values: dict[str, Any]) -> None:
        for field, value in values.items():
            setattr(record, field, value)

    @staticmethod
    def _validate_merged_date_range(
        record: Any,
        values: dict[str, Any],
        label: str,
        *,
        start_field: str = "valid_from",
        end_field: str = "valid_to",
    ) -> None:
        start_value = values.get(start_field, getattr(record, start_field))
        end_value = values.get(end_field, getattr(record, end_field))
        if start_value and end_value and start_value > end_value:
            raise AppException(
                f"{label}开始日期不能晚于结束日期",
                code=42221,
                status_code=422,
            )

    @staticmethod
    def _certificate_valid_condition() -> Any:
        today = date.today()
        return and_(
            QualificationCertificate.status == CertificateStatus.VALID,
            or_(
                QualificationCertificate.valid_from.is_(None),
                QualificationCertificate.valid_from <= today,
            ),
            or_(
                QualificationCertificate.valid_to.is_(None),
                QualificationCertificate.valid_to >= today,
            ),
        )

    @staticmethod
    def _personnel_valid_condition() -> Any:
        today = date.today()
        return and_(
            PersonnelCertificate.is_on_job.is_(True),
            or_(
                PersonnelCertificate.valid_from.is_(None),
                PersonnelCertificate.valid_from <= today,
            ),
            or_(
                PersonnelCertificate.valid_to.is_(None),
                PersonnelCertificate.valid_to >= today,
            ),
        )
