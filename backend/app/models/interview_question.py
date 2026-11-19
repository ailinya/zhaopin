"""
InterviewQuestion 模型 + Repository

面试题目 + 候选人答案。

字段：
- difficulty: "hard" / "medium" / "easy"（LLM 出题时分类）
- answer_audio: BLOB 或文件路径（Week 2 起切文件路径）
- answer_text: Whisper 转写后的文本
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy import func, case

from app.database import Base


class InterviewQuestion(Base):
    """面试题目"""
    __tablename__ = "interview_questions"

    # ===== 主键 =====
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ===== 业务字段 =====
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    score_standard: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== 难度（§10.4 节点 A 输出）=====
    # "hard" / "medium" / "easy"
    difficulty: Mapped[str] = mapped_column(String, default="medium")

    # ===== 答案 =====
    # 音频 BLOB（保留兼容，Week 2 切文件）
    answer_audio: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # 音频文件路径（新写入用）
    answer_audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Whisper 转写后的文本
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===== 时间戳 =====
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    answered_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        answered = "✓" if self.answered_at else "○"
        return f"<Question {self.id} [{self.difficulty}] {answered}: {self.question[:30]}...>"


# ===== Repository =====
class InterviewQuestionRepository:
    """InterviewQuestion 数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, question_id: int) -> InterviewQuestion | None:
        return self.db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()

    def get_next(self, interview_id: int, after_id: int) -> InterviewQuestion | None:
        """获取下一题（id > after_id 的第一个未答题）

        必须过滤 answered_at IS NULL，否则已答题会被当作"下一题"返回，
        候选人录音提交后会被后端 409 拒绝（INVALID_STATE_TRANSITION）。
        """
        return (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == interview_id)
            .filter(InterviewQuestion.id > after_id)
            .filter(InterviewQuestion.answered_at.is_(None))
            .order_by(InterviewQuestion.id.asc())
            .first()
        )

    def list_by_interview(self, interview_id: int) -> list[InterviewQuestion]:
        """获取面试的全部题目（按 id 升序）"""
        return (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == interview_id)
            .order_by(InterviewQuestion.id.asc())
            .all()
        )

    def list_unanswered(self, interview_id: int) -> list[InterviewQuestion]:
        """获取未回答的题目"""
        return (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == interview_id)
            .filter(InterviewQuestion.answered_at.is_(None))
            .order_by(InterviewQuestion.id.asc())
            .all()
        )

    def count_by_interview(self, interview_id: int) -> int:
        """总题目数"""
        return (
            self.db.query(func.count(InterviewQuestion.id))
            .filter(InterviewQuestion.interview_id == interview_id)
            .scalar()
        ) or 0

    def count_answered(self, interview_id: int) -> int:
        """已答题数"""
        return (
            self.db.query(func.count(InterviewQuestion.id))
            .filter(InterviewQuestion.interview_id == interview_id)
            .filter(InterviewQuestion.answered_at.isnot(None))
            .scalar()
        ) or 0

    def create(
        self,
        interview_id: int,
        question: str,
        score_standard: str | None = None,
        difficulty: str = "medium",
    ) -> InterviewQuestion:
        question_obj = InterviewQuestion(
            interview_id=interview_id,
            question=question,
            score_standard=score_standard,
            difficulty=difficulty,
        )
        self.db.add(question_obj)
        self.db.commit()
        self.db.refresh(question_obj)
        return question_obj

    def bulk_create(
        self,
        interview_id: int,
        questions: list[dict],
    ) -> list[InterviewQuestion]:
        """批量创建题目（节点 A 出题后调用）"""
        objs = [
            InterviewQuestion(
                interview_id=interview_id,
                question=q["question"],
                score_standard=q.get("score_standard"),
                difficulty=q.get("difficulty", "medium"),
            )
            for q in questions
        ]
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        return objs

    def update_answer(
        self,
        question_id: int,
        answer_text: str,
        answer_audio: bytes | None = None,
        answer_audio_path: str | None = None,
    ) -> InterviewQuestion | None:
        """提交答案（§10.6 submit_answer 端点调用）"""
        question = self.get(question_id)
        if not question:
            return None
        question.answer_text = answer_text
        if answer_audio is not None:
            question.answer_audio = answer_audio
        if answer_audio_path is not None:
            question.answer_audio_path = answer_audio_path
        question.answered_at = int(datetime.utcnow().timestamp())
        self.db.commit()
        self.db.refresh(question)
        return question

    def delete_by_interview(self, interview_id: int) -> int:
        """删除面试的全部题目（删除面试时级联调用）"""
        count = (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == interview_id)
            .delete()
        )
        # 不在这里commit，由service层统一提交
        return count