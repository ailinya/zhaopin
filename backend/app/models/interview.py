"""
Interview 模型 + Repository

面试实体。HR 创建面试 → LangGraph 出题 → 候选人答题 → 生成报告。

关键字段（§4 行动项 #2 + §10.3）：
- status: 0=未开始 / 1=试题已备好 / 2=进行中 / 3=完毕 / 4=报告已生成
- langgraph_thread_id: UUID，与 LangGraph checkpointer 关联
- answered_count: 实时进度计数（替代 COUNT 查询）
- total_hard_questions / total_medium_questions / total_easy_questions: 难度计数
- token: 32 位候选人 URL token
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base
from app.core.security import generate_candidate_token


class Interview(Base):
    """面试"""
    __tablename__ = "interviews"

    # ===== 主键 =====
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ===== 业务字段 =====
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    interviewer: Mapped[str | None] = mapped_column(String, nullable=True)

    # ===== 时间 =====
    start_time: Mapped[int] = mapped_column(Integer)  # Unix 时间戳
    end_time: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ===== 状态机（§10.3）=====
    # 0=未开始 / 1=试题已备好 / 2=进行中 / 3=完毕 / 4=报告已生成
    status: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # ===== 题目相关 =====
    question_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 实时进度计数（§4 行动项 #2：替代 COUNT 查询）
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    # 难度计数
    total_hard_questions: Mapped[int] = mapped_column(Integer, default=0)
    total_medium_questions: Mapped[int] = mapped_column(Integer, default=0)
    total_easy_questions: Mapped[int] = mapped_column(Integer, default=0)

    # ===== 结果 / 配置 =====
    is_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voice_reading: Mapped[int] = mapped_column(Integer, default=1)  # 0=关闭 / 1=开启

    # ===== 报告存储 =====
    # 老 BLOB（Phase 4 切文件后废弃）
    report_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # 新文件路径
    report_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # ===== 鉴权 + 工作流 =====
    # 候选人 URL 鉴权 token（32 位字母数字）
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    # LangGraph checkpoint thread_id（§4 行动项 #2）
    langgraph_thread_id: Mapped[str] = mapped_column(
        String,
        default=lambda: str(uuid.uuid4()),
        unique=True,
    )

    # ===== 时间戳 =====
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at: Mapped[int] = mapped_column(
        Integer,
        default=lambda: int(datetime.utcnow().timestamp()),
        onupdate=lambda: int(datetime.utcnow().timestamp()),
    )

    def __repr__(self) -> str:
        return f"<Interview {self.id}: status={self.status}, answered={self.answered_count}/{self.question_count}>"

    @property
    def is_active(self) -> bool:
        """面试是否进行中（status 1-3 都算活跃）"""
        return 1 <= self.status <= 3


# ===== Repository =====
class InterviewRepository:
    """Interview 数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, interview_id: int) -> Interview | None:
        return self.db.query(Interview).filter(Interview.id == interview_id).first()

    def get_by_token(self, token: str) -> Interview | None:
        """通过候选人 URL token 查面试（§14.7 鉴权依赖用）"""
        return self.db.query(Interview).filter(Interview.token == token).first()

    def list_all(
        self,
        candidate_id: str | None = None,
        position_id: int | None = None,
        status: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Interview]:
        query = self.db.query(Interview)
        if candidate_id is not None:
            query = query.filter(Interview.candidate_id == candidate_id)
        if position_id is not None:
            query = query.filter(Interview.position_id == position_id)
        if status is not None:
            query = query.filter(Interview.status == status)
        return query.order_by(Interview.id.desc()).offset(skip).limit(limit).all()

    def list_by_status(
        self,
        statuses: list[int],
        older_than_minutes: int | None = None,
    ) -> list[Interview]:
        """按状态列表查（如卡住巡检用，§10.7）"""
        from datetime import datetime, timedelta
        query = self.db.query(Interview).filter(Interview.status.in_(statuses))
        if older_than_minutes is not None:
            threshold = int((datetime.utcnow() - timedelta(minutes=older_than_minutes)).timestamp())
            query = query.filter(Interview.updated_at < threshold)
        return query.all()

    def create(
        self,
        candidate_id: str,
        position_id: int,
        start_time: int,
        interviewer: str | None = None,
        token: str | None = None,
        token_length: int = 32,
    ) -> Interview:
        """创建面试（自动生成 token + langgraph_thread_id）"""
        now = int(datetime.utcnow().timestamp())
        interview = Interview(
            candidate_id=candidate_id,
            position_id=position_id,
            start_time=start_time,
            interviewer=interviewer,
            status=0,  # 未开始
            token=token or generate_candidate_token(token_length),
            created_at=now,
            updated_at=now,
        )
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def update_status(
        self,
        interview_id: int,
        status: int,
    ) -> Interview | None:
        """更新状态（同时 touch updated_at）"""
        interview = self.get(interview_id)
        if not interview:
            return None
        interview.status = status
        interview.updated_at = int(datetime.utcnow().timestamp())
        if status == 3:  # 完毕
            interview.end_time = interview.updated_at
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def update_questions_generated(
        self,
        interview_id: int,
        question_count: int,
        difficulty_distribution: dict[str, int],
    ) -> Interview | None:
        """节点 A 出题完成后调用（§10.4）"""
        interview = self.get(interview_id)
        if not interview:
            return None
        interview.status = 1  # 试题已备好
        interview.question_count = question_count
        interview.total_hard_questions = difficulty_distribution.get("hard", 0)
        interview.total_medium_questions = difficulty_distribution.get("medium", 0)
        interview.total_easy_questions = difficulty_distribution.get("easy", 0)
        interview.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def increment_answered(self, interview_id: int) -> Interview | None:
        """答完一题后 +1（§10.6）

        状态机：
        - 1 → 2：候选人开始作答（首题答完后）
        - 2 → 3：所有题答完
        """
        interview = self.get(interview_id)
        if not interview:
            return None
        interview.answered_count += 1

        # 1 → 2：开始答题
        if interview.status == 1:
            interview.status = 2

        # 2 → 3：全部答完
        if (
            interview.question_count is not None
            and interview.answered_count >= interview.question_count
        ):
            interview.status = 3
            interview.end_time = int(datetime.utcnow().timestamp())

        interview.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def update_report(
        self,
        interview_id: int,
        report_path: str,
        report_content: bytes | None = None,
        is_passed: int | None = None,
    ) -> Interview | None:
        """节点 D 报告生成完成后调用"""
        interview = self.get(interview_id)
        if not interview:
            return None
        interview.status = 4  # 报告已生成
        interview.report_path = report_path
        if report_content is not None:
            interview.report_content = report_content
        if is_passed is not None:
            interview.is_passed = is_passed
        interview.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def update_voice_reading(
        self,
        interview_id: int,
        enabled: bool,
    ) -> Interview | None:
        """切换候选人语音朗读"""
        interview = self.get(interview_id)
        if not interview:
            return None
        interview.voice_reading = 1 if enabled else 0
        interview.updated_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def delete(self, interview_id: int) -> bool:
        """删除面试（级联删除题目在 API 层处理）"""
        interview = self.get(interview_id)
        if not interview:
            return False
        self.db.delete(interview)
        # 不在这里commit，由service层统一提交
        return True