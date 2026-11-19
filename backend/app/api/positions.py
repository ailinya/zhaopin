"""
Positions API（§1.1 + §12）

端点（HR 端，JWT 鉴权）：
- GET    /api/positions              列表（分页 + status 过滤）
- POST   /api/positions              创建
- GET    /api/positions/{id}         详情
- PUT    /api/positions/{id}         更新
- DELETE /api/positions/{id}         删除
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.position import (
    PositionCreate,
    PositionUpdate,
    PositionOut,
    PositionListResponse,
)
from app.schemas.response import APIResponse
from app.services.position_service import PositionService


router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("", response_model=APIResponse[PositionListResponse])
async def list_positions(
    status: int | None = Query(default=None, ge=0, le=2, description="0=未启动/1=进行中/2=已完成"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取岗位列表"""
    service = PositionService(db, actor_id=user.id)
    skip = (page - 1) * page_size
    items, total = service.list_positions(status=status, skip=skip, limit=page_size)
    return APIResponse.ok(
        PositionListResponse(
            items=[PositionOut.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=APIResponse[PositionOut], status_code=201)
async def create_position(
    data: PositionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建岗位"""
    service = PositionService(db, actor_id=user.id)
    position = service.create_position(
        name=data.name,
        requirements=data.requirements,
        responsibilities=data.responsibilities,
        quantity=data.quantity,
        status=data.status,
        recruiter=data.recruiter or user.username,
    )
    return APIResponse.ok(PositionOut.model_validate(position))


@router.get("/{position_id}", response_model=APIResponse[PositionOut])
async def get_position(
    position_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取岗位详情"""
    service = PositionService(db, actor_id=user.id)
    position = service.get_position(position_id)
    return APIResponse.ok(PositionOut.model_validate(position))


@router.put("/{position_id}", response_model=APIResponse[PositionOut])
async def update_position(
    position_id: int,
    data: PositionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新岗位"""
    service = PositionService(db, actor_id=user.id)
    position = service.update_position(
        position_id,
        name=data.name,
        requirements=data.requirements,
        responsibilities=data.responsibilities,
        quantity=data.quantity,
        status=data.status,
        recruiter=data.recruiter,
    )
    return APIResponse.ok(PositionOut.model_validate(position))


@router.delete("/{position_id}", response_model=APIResponse[dict])
async def delete_position(
    position_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除岗位（有关联候选人/面试时拒绝）"""
    service = PositionService(db, actor_id=user.id)
    service.delete_position(position_id)
    return APIResponse.ok({"status": "deleted", "position_id": position_id})