"""
Position 业务服务层（§1.1）

业务规则：
- 创建岗位时 status 默认 0（未启动）
- 更新时记录操作到 AuditLog
- 删除前检查关联候选人/面试（不允许删除有关联的岗位）
"""
from sqlalchemy.orm import Session

from app.core.errors import APIError, ErrorCode
from app.models import Position, PositionRepository, AuditLogRepository


class PositionService:
    """Position 业务服务"""

    def __init__(self, db: Session, actor_id: str = "system"):
        self.db = db
        self.repo = PositionRepository(db)
        self.audit = AuditLogRepository(db)
        self.actor_id = actor_id

    def list_positions(
        self,
        status: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Position], int]:
        """获取岗位列表 + 总数"""
        items = self.repo.list_all(status=status, skip=skip, limit=limit)
        # total: 简化为当前 limit 内的数量（Phase 2 用 cursor pagination + 独立 count）
        total = len(self.repo.list_all(status=status, skip=0, limit=10000))
        return items, total

    def get_position(self, position_id: int) -> Position:
        """获取岗位（不存在则 404）"""
        position = self.repo.get(position_id)
        if not position:
            raise APIError.not_found(
                ErrorCode.POSITION_NOT_FOUND,
                f"岗位 {position_id} 不存在",
            )
        return position

    def create_position(
        self,
        name: str,
        requirements: str = "",
        responsibilities: str = "",
        quantity: int = 1,
        status: int = 0,
        recruiter: str | None = None,
    ) -> Position:
        """创建岗位"""
        if not name or not name.strip():
            raise APIError.bad_request(
                ErrorCode.PARAM_MISSING, "岗位名称不能为空"
            )
        if quantity < 1:
            raise APIError.bad_request(
                ErrorCode.PARAM_OUT_OF_RANGE, "需求人数必须 ≥ 1"
            )
        if status not in (0, 1, 2):
            raise APIError.bad_request(
                ErrorCode.PARAM_OUT_OF_RANGE, "status 必须是 0/1/2"
            )

        position = self.repo.create(
            name=name.strip(),
            requirements=requirements,
            responsibilities=responsibilities,
            quantity=quantity,
            status=status,
            recruiter=recruiter,
        )

        self.audit.create(
            event_type="position_created",
            actor_id=self.actor_id,
            actor_type="user",
            metadata={"position_id": position.id, "name": position.name},
        )
        return position

    def update_position(
        self,
        position_id: int,
        name: str | None = None,
        requirements: str | None = None,
        responsibilities: str | None = None,
        quantity: int | None = None,
        status: int | None = None,
        recruiter: str | None = None,
    ) -> Position:
        """更新岗位"""
        self.get_position(position_id)  # 验证存在（404）
        if status is not None and status not in (0, 1, 2):
            raise APIError.bad_request(
                ErrorCode.PARAM_OUT_OF_RANGE, "status 必须是 0/1/2"
            )

        updated = self.repo.update(
            position_id,
            name=name,
            requirements=requirements,
            responsibilities=responsibilities,
            quantity=quantity,
            status=status,
            recruiter=recruiter,
        )

        self.audit.create(
            event_type="position_updated",
            actor_id=self.actor_id,
            actor_type="user",
            metadata={"position_id": position_id, "fields": list(
                k for k, v in {
                    "name": name, "requirements": requirements,
                    "responsibilities": responsibilities, "quantity": quantity,
                    "status": status, "recruiter": recruiter,
                }.items() if v is not None
            )},
        )
        return updated

    def delete_position(self, position_id: int) -> None:
        """删除岗位（有关联候选人/面试时拒绝）"""
        position = self.get_position(position_id)

        # 检查关联
        from app.models.candidate import CandidateRepository
        candidates = CandidateRepository(self.db).list_by_position(position_id)
        if candidates:
            raise APIError.conflict(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"岗位下还有 {len(candidates)} 个候选人，无法删除",
            )

        from app.models.interview import InterviewRepository
        interviews = InterviewRepository(self.db).list_all(position_id=position_id)
        if interviews:
            raise APIError.conflict(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"岗位下还有 {len(interviews)} 个面试，无法删除",
            )

        self.repo.delete(position_id)

        self.audit.create(
            event_type="position_deleted",
            actor_id=self.actor_id,
            actor_type="user",
            metadata={"position_id": position_id, "name": position.name},
        )