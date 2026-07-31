from fastapi import APIRouter

from app.api.v1 import agent, files, qualifications, settings, skills, tasks, templates


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tasks.router)
api_router.include_router(files.router)
api_router.include_router(qualifications.router)
api_router.include_router(skills.router)
api_router.include_router(agent.router)
api_router.include_router(settings.router)
api_router.include_router(templates.router)
