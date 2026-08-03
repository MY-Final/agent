from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.api.v1 import (
    agent,
    auth,
    dashboard,
    files,
    qualifications,
    runtime,
    settings,
    skills,
    stats,
    tasks,
    templates,
)


api_router = APIRouter(prefix="/api/v1")

# 业务接口统一要求认证：未携带有效 Token 一律返回 401
protected = APIRouter(dependencies=[Depends(require_auth)])
protected.include_router(tasks.router)
protected.include_router(dashboard.router)
protected.include_router(files.router)
protected.include_router(qualifications.router)
protected.include_router(skills.router)
protected.include_router(agent.router)
protected.include_router(settings.router)
protected.include_router(templates.router)
protected.include_router(stats.router)
protected.include_router(runtime.router)
api_router.include_router(protected)

# 认证接口：登录放行，修改密码/退出登录需登录
api_router.include_router(auth.router)
