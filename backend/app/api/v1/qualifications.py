import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.models.qualification import CertificateStatus
from app.schemas.qualification import (
    CertificateListData,
    CompanyListData,
    CompanyProfileCreate,
    CompanyProfileRead,
    CompanyProfileUpdate,
    PerformanceListData,
    PerformanceRecordCreate,
    PerformanceRecordRead,
    PerformanceRecordUpdate,
    PersonnelCertificateCreate,
    PersonnelCertificateRead,
    PersonnelCertificateUpdate,
    PersonnelListData,
    QualificationCertificateCreate,
    QualificationCertificateRead,
    QualificationCertificateUpdate,
)
from app.schemas.task import DeleteResult
from app.services.qualification_service import QualificationService


router = APIRouter(prefix="/qualifications", tags=["公司资质知识库"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PageDep = Annotated[int, Query(ge=1)]
PageSizeDep = Annotated[int, Query(ge=1, le=100)]


@router.post(
    "/certificates",
    response_model=ApiResponse[QualificationCertificateRead],
    status_code=status.HTTP_201_CREATED,
    summary="新增资质证书",
)
async def create_certificate(
    payload: QualificationCertificateCreate,
    session: SessionDep,
) -> ApiResponse[QualificationCertificateRead]:
    record = await QualificationService.create_certificate(session, payload)
    return success_response(
        QualificationCertificateRead.model_validate(record),
        msg="资质证书创建成功",
    )


@router.get(
    "/certificates",
    response_model=ApiResponse[CertificateListData],
    summary="查询资质证书",
)
async def list_certificates(
    session: SessionDep,
    name: str | None = None,
    certificate_status: Annotated[CertificateStatus | None, Query(alias="status")] = None,
    is_valid: bool | None = None,
    page: PageDep = 1,
    page_size: PageSizeDep = 20,
) -> ApiResponse[CertificateListData]:
    records, total = await QualificationService.list_certificates(
        session,
        name=name,
        status=certificate_status,
        is_valid=is_valid,
        page=page,
        page_size=page_size,
    )
    items = [QualificationCertificateRead.model_validate(item) for item in records]
    return success_response(
        CertificateListData.build(items, total, page, page_size)
    )


@router.get(
    "/certificates/{record_id}",
    response_model=ApiResponse[QualificationCertificateRead],
    summary="获取资质证书详情",
)
async def get_certificate(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[QualificationCertificateRead]:
    record = await QualificationService.get_certificate(session, record_id)
    return success_response(QualificationCertificateRead.model_validate(record))


@router.put(
    "/certificates/{record_id}",
    response_model=ApiResponse[QualificationCertificateRead],
    summary="更新资质证书",
)
async def update_certificate(
    record_id: uuid.UUID,
    payload: QualificationCertificateUpdate,
    session: SessionDep,
) -> ApiResponse[QualificationCertificateRead]:
    record = await QualificationService.update_certificate(session, record_id, payload)
    return success_response(
        QualificationCertificateRead.model_validate(record),
        msg="资质证书更新成功",
    )


@router.delete(
    "/certificates/{record_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除资质证书",
)
async def delete_certificate(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await QualificationService.delete_certificate(session, minio_storage, record_id)
    return success_response(DeleteResult(id=record_id), msg="资质证书删除成功")


@router.post(
    "/performances",
    response_model=ApiResponse[PerformanceRecordRead],
    status_code=status.HTTP_201_CREATED,
    summary="新增业绩记录",
)
async def create_performance(
    payload: PerformanceRecordCreate,
    session: SessionDep,
) -> ApiResponse[PerformanceRecordRead]:
    record = await QualificationService.create_performance(session, payload)
    return success_response(
        PerformanceRecordRead.model_validate(record),
        msg="业绩记录创建成功",
    )


@router.get(
    "/performances",
    response_model=ApiResponse[PerformanceListData],
    summary="查询业绩记录",
)
async def list_performances(
    session: SessionDep,
    keyword: str | None = None,
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    is_completed: bool | None = None,
    page: PageDep = 1,
    page_size: PageSizeDep = 20,
) -> ApiResponse[PerformanceListData]:
    records, total = await QualificationService.list_performances(
        session,
        keyword=keyword,
        min_amount=min_amount,
        max_amount=max_amount,
        is_completed=is_completed,
        page=page,
        page_size=page_size,
    )
    items = [PerformanceRecordRead.model_validate(item) for item in records]
    return success_response(PerformanceListData.build(items, total, page, page_size))


@router.get(
    "/performances/{record_id}",
    response_model=ApiResponse[PerformanceRecordRead],
    summary="获取业绩详情",
)
async def get_performance(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[PerformanceRecordRead]:
    record = await QualificationService.get_performance(session, record_id)
    return success_response(PerformanceRecordRead.model_validate(record))


@router.put(
    "/performances/{record_id}",
    response_model=ApiResponse[PerformanceRecordRead],
    summary="更新业绩记录",
)
async def update_performance(
    record_id: uuid.UUID,
    payload: PerformanceRecordUpdate,
    session: SessionDep,
) -> ApiResponse[PerformanceRecordRead]:
    record = await QualificationService.update_performance(session, record_id, payload)
    return success_response(
        PerformanceRecordRead.model_validate(record),
        msg="业绩记录更新成功",
    )


@router.delete(
    "/performances/{record_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除业绩记录",
)
async def delete_performance(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await QualificationService.delete_performance(session, minio_storage, record_id)
    return success_response(DeleteResult(id=record_id), msg="业绩记录删除成功")


@router.post(
    "/personnel",
    response_model=ApiResponse[PersonnelCertificateRead],
    status_code=status.HTTP_201_CREATED,
    summary="新增人员证书",
)
async def create_personnel(
    payload: PersonnelCertificateCreate,
    session: SessionDep,
) -> ApiResponse[PersonnelCertificateRead]:
    record = await QualificationService.create_personnel(session, payload)
    return success_response(
        PersonnelCertificateRead.model_validate(record),
        msg="人员证书创建成功",
    )


@router.get(
    "/personnel",
    response_model=ApiResponse[PersonnelListData],
    summary="查询人员证书",
)
async def list_personnel(
    session: SessionDep,
    person_name: str | None = None,
    cert_type: str | None = None,
    specialty: str | None = None,
    is_on_job: bool | None = None,
    is_valid: bool | None = None,
    page: PageDep = 1,
    page_size: PageSizeDep = 20,
) -> ApiResponse[PersonnelListData]:
    records, total = await QualificationService.list_personnel(
        session,
        person_name=person_name,
        cert_type=cert_type,
        specialty=specialty,
        is_on_job=is_on_job,
        is_valid=is_valid,
        page=page,
        page_size=page_size,
    )
    items = [PersonnelCertificateRead.model_validate(item) for item in records]
    return success_response(PersonnelListData.build(items, total, page, page_size))


@router.get(
    "/personnel/{record_id}",
    response_model=ApiResponse[PersonnelCertificateRead],
    summary="获取人员证书详情",
)
async def get_personnel(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[PersonnelCertificateRead]:
    record = await QualificationService.get_personnel(session, record_id)
    return success_response(PersonnelCertificateRead.model_validate(record))


@router.put(
    "/personnel/{record_id}",
    response_model=ApiResponse[PersonnelCertificateRead],
    summary="更新人员证书",
)
async def update_personnel(
    record_id: uuid.UUID,
    payload: PersonnelCertificateUpdate,
    session: SessionDep,
) -> ApiResponse[PersonnelCertificateRead]:
    record = await QualificationService.update_personnel(session, record_id, payload)
    return success_response(
        PersonnelCertificateRead.model_validate(record),
        msg="人员证书更新成功",
    )


@router.delete(
    "/personnel/{record_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除人员证书",
)
async def delete_personnel(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await QualificationService.delete_personnel(session, minio_storage, record_id)
    return success_response(DeleteResult(id=record_id), msg="人员证书删除成功")


@router.post(
    "/company",
    response_model=ApiResponse[CompanyProfileRead],
    status_code=status.HTTP_201_CREATED,
    summary="新增公司信息",
)
async def create_company(
    payload: CompanyProfileCreate,
    session: SessionDep,
) -> ApiResponse[CompanyProfileRead]:
    record = await QualificationService.create_company(session, payload)
    return success_response(
        CompanyProfileRead.model_validate(record),
        msg="公司信息创建成功",
    )


@router.get(
    "/company",
    response_model=ApiResponse[CompanyListData],
    summary="查询公司信息",
)
async def list_companies(
    session: SessionDep,
    company_name: str | None = None,
    page: PageDep = 1,
    page_size: PageSizeDep = 20,
) -> ApiResponse[CompanyListData]:
    records, total = await QualificationService.list_companies(
        session,
        company_name=company_name,
        page=page,
        page_size=page_size,
    )
    items = [CompanyProfileRead.model_validate(item) for item in records]
    return success_response(CompanyListData.build(items, total, page, page_size))


@router.get(
    "/company/{record_id}",
    response_model=ApiResponse[CompanyProfileRead],
    summary="获取公司信息详情",
)
async def get_company(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[CompanyProfileRead]:
    record = await QualificationService.get_company(session, record_id)
    return success_response(CompanyProfileRead.model_validate(record))


@router.put(
    "/company/{record_id}",
    response_model=ApiResponse[CompanyProfileRead],
    summary="更新公司信息",
)
async def update_company(
    record_id: uuid.UUID,
    payload: CompanyProfileUpdate,
    session: SessionDep,
) -> ApiResponse[CompanyProfileRead]:
    record = await QualificationService.update_company(session, record_id, payload)
    return success_response(
        CompanyProfileRead.model_validate(record),
        msg="公司信息更新成功",
    )


@router.delete(
    "/company/{record_id}",
    response_model=ApiResponse[DeleteResult],
    summary="删除公司信息",
)
async def delete_company(
    record_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[DeleteResult]:
    await QualificationService.delete_company(session, record_id)
    return success_response(DeleteResult(id=record_id), msg="公司信息删除成功")
