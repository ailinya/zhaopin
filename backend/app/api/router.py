"""
API Router 聚合（§1.1）

所有子路由集中注册，前缀统一为 /api。
"""
from fastapi import APIRouter

from app.api import auth, positions, candidates, interviews, candidate_portal, events


api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(positions.router)
api_router.include_router(candidates.router)
api_router.include_router(interviews.router)
api_router.include_router(candidate_portal.router)
api_router.include_router(events.router)