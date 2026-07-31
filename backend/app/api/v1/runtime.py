from fastapi import APIRouter

from app.core.response import ApiResponse, success_response
from app.schemas.runtime import (
    RuntimeSettingsInput,
    RuntimeSettingsRead,
    RuntimeTestResult,
)
from app.services.runtime_settings_service import RuntimeSettingsService


router = APIRouter(prefix="/runtime", tags=["系统设置 - 基础设施"])


@router.get(
    "/settings",
    response_model=ApiResponse[RuntimeSettingsRead],
    summary="获取基础设施配置与连接状态",
)
async def get_runtime_settings() -> ApiResponse[RuntimeSettingsRead]:
    return success_response(await RuntimeSettingsService.get_read())


@router.post(
    "/settings/test",
    response_model=ApiResponse[RuntimeTestResult],
    summary="测试基础设施连接（不保存）",
)
async def test_runtime_settings(
    payload: RuntimeSettingsInput,
) -> ApiResponse[RuntimeTestResult]:
    return success_response(
        await RuntimeSettingsService.test(payload),
        msg="连接测试完成",
    )


@router.put(
    "/settings",
    response_model=ApiResponse[RuntimeSettingsRead],
    summary="保存基础设施配置并测试连接",
)
async def save_runtime_settings(
    payload: RuntimeSettingsInput,
) -> ApiResponse[RuntimeSettingsRead]:
    data = await RuntimeSettingsService.save(payload)
    return success_response(data, msg="基础设施配置已保存，重启后端后生效")
