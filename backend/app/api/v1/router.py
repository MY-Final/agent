from fastapi import APIRouter

from app.api.v1 import files, skills, tasks


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tasks.router)
api_router.include_router(files.router)
api_router.include_router(skills.router)
