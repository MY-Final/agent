"""通用认证依赖。"""

from fastapi import Header

from app.core.auth import verify_token
from app.core.exceptions import AppException


def require_auth(authorization: str | None = Header(default=None)) -> str:
    """校验 Authorization: Bearer <token>，返回当前用户名。"""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppException("未登录或登录已过期", code=40100, status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    username = verify_token(token)
    if not username:
        raise AppException("未登录或登录已过期", code=40100, status_code=401)
    return username
