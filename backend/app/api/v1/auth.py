"""认证相关接口：登录、修改密码、退出登录。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.auth import change_password, create_token, verify_login
from app.core.exceptions import AppException
from app.core.response import ApiResponse, success_response

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class LoginData(BaseModel):
    token: str
    username: str
    must_change_password: bool


@router.post("/login", response_model=ApiResponse[LoginData], summary="账号密码登录")
async def login(payload: LoginRequest) -> ApiResponse[LoginData]:
    user = verify_login(payload.username, payload.password)
    if not user:
        raise AppException("账号或密码错误", code=40100, status_code=401)
    token = create_token(user["username"])
    return success_response(
        LoginData(
            token=token,
            username=user["username"],
            must_change_password=user["must_change_password"],
        ),
        msg="登录成功",
    )


@router.post(
    "/change-password",
    response_model=ApiResponse[None],
    summary="修改密码（需登录）",
)
async def change_password_endpoint(
    payload: ChangePasswordRequest,
    username: str = Depends(require_auth),
) -> ApiResponse[None]:
    change_password(username, payload.old_password, payload.new_password)
    return success_response(msg="密码修改成功")


@router.post("/logout", response_model=ApiResponse[None], summary="退出登录")
async def logout(username: str = Depends(require_auth)) -> ApiResponse[None]:
    return success_response(msg="已退出登录")
