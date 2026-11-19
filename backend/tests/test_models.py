"""
Models 测试

覆盖所有 6 张表的 CRUD + 关系 + 默认值。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import (
    User,
    Position,
    Candidate,
    Interview,
    InterviewQuestion,
    AuditLog,
    UserRepository,
    PositionRepository,
    CandidateRepository,
    InterviewRepository,
    InterviewQuestionRepository,
    AuditLogRepository,
)
from app.core.security import verify_password


# ===== Fixtures =====

@pytest.fixture(scope="function")
def db():
    """内存 SQLite 数据库 fixture（每个测试函数独立的隔离 DB）

    用 StaticPool 让所有连接共享同一内存 DB
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 监听 connect 事件，启用 SQLite PRAGMA（WAL + foreign_keys）
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    # Session 工厂
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ===== User 测试 =====

def test_user_create(db: Session):
    """User 创建 + 默认值"""
    repo = UserRepository(db)
    user = repo.create(
        id="user-1",
        username="admin",
        email="admin@example.com",
        password="123456",
        full_name="张三",
    )
    assert user.id == "user-1"
    assert user.username == "admin"
    assert user.email == "admin@example.com"
    assert user.is_active is True
    assert user.is_admin is False
    assert user.full_name == "张三"
    assert verify_password("123456", user.password_hash)


def test_user_unique_username(db: Session):
    """用户名唯一性"""
    from sqlalchemy.exc import IntegrityError

    repo = UserRepository(db)
    repo.create(id="user-1", username="admin", email="admin@example.com", password="123456")
    db.commit()

    with pytest.raises(IntegrityError):
        repo.create(id="user-2", username="admin", email="hr002@example.com", password="secret456")
        db.commit()


def test_user_get_by_username(db: Session):
    """按用户名查询"""
    repo = UserRepository(db)
    repo.create(id="user-1", username="admin", email="admin@example.com", password="x")

    user = repo.get_by_username("admin")
    assert user is not None
    assert user.id == "user-1"

    assert repo.get_by_username("nonexistent") is None


def test_user_update_last_login(db: Session):
    """更新最后登录时间"""
    repo = UserRepository(db)
    repo.create(id="user-1", username="admin", email="admin@example.com", password="x")

    assert repo.get("user-1").last_login_at is None
    repo.update_last_login("user-1")
    assert repo.get("user-1").last_login_at is not None


# ===== Position 测试 =====

def test_position_create(db: Session):
    """Position 创建 + 默认值"""
    repo = PositionRepository(db)
    pos = repo.create(
        name="前端工程师",
        requirements="熟悉 Vue/React",
        responsibilities="开发 Web 应用",
        quantity=2,
        recruiter="admin",
    )
    assert pos.id is not None
    assert pos.name == "前端工程师"
    assert pos.quantity == 2
    assert pos.status == 0  # 默认未启动


def test_position_update(db: Session):
    """Position 更新"""
    repo = PositionRepository(db)
    pos = repo.create(name="P1")
    pos_id = pos.id

    updated = repo.update(pos_id, name="P1 renamed", status=1)
    assert updated.name == "P1 renamed"
    assert updated.status == 1


def test_position_list_by_status(db: Session):
    """按状态过滤"""
    repo = PositionRepository(db)
    repo.create(name="P1", status=0)
    repo.create(name="P2", status=1)
    repo.create(name="P3", status=1)

    active = repo.list_all(status=1)
    assert len(active) == 2
    assert all(p.status == 1 for p in active)


def test_position_delete(db: Session):
    """Position 删除"""
    repo = PositionRepository(db)
    pos = repo.create(name="To delete")
    pos_id = pos.id

    assert repo.delete(pos_id) is True
    assert repo.get(pos_id) is None
    assert repo.delete(pos_id) is False  # 不存在的


# ===== Candidate 测试 =====

def test_candidate_create(db: Session):
    """Candidate 创建"""
    pos = PositionRepository(db).create(name="P1")

    repo = CandidateRepository(db)
    cand = repo.create(
        id="cand-1",
        position_id=pos.id,
        name="李四",
        email="li@example.com",
        resume_type=0,  # PDF
        uploaded_by="admin",
        resume_path="/path/to/resume.pdf",
    )
    assert cand.id == "cand-1"
    assert cand.parse_status == 1  # 默认解析中
    assert cand.is_scanned_document is False


def test_candidate_update_parse_status(db: Session):
    """更新解析状态（§11 简历解析专用）"""
    pos = PositionRepository(db).create(name="P1")
    repo = CandidateRepository(db)
    cand = repo.create(
        id="cand-1",
        position_id=pos.id,
        name="李四",
        email="li@example.com",
        resume_type=0,
        uploaded_by="admin",
    )

    # 解析成功
    updated = repo.update_parse_status(
        cand.id,
        parse_status=2,
        resume_text="李四的简历内容...",
    )
    assert updated.parse_status == 2
    assert updated.resume_text == "李四的简历内容..."
    assert updated.parsed_at is not None

    # 解析失败
    updated = repo.update_parse_status(
        cand.id,
        parse_status=3,
        parse_error="扫描件 PDF",
    )
    assert updated.parse_status == 3
    assert updated.parse_error == "扫描件 PDF"


def test_candidate_list_by_position(db: Session):
    """按岗位过滤候选人"""
    pos1 = PositionRepository(db).create(name="P1")
    pos2 = PositionRepository(db).create(name="P2")

    repo = CandidateRepository(db)
    repo.create(id="c1", position_id=pos1.id, name="A", email="a@x.com", resume_type=0, uploaded_by="hr1")
    repo.create(id="c2", position_id=pos1.id, name="B", email="b@x.com", resume_type=0, uploaded_by="hr1")
    repo.create(id="c3", position_id=pos2.id, name="C", email="c@x.com", resume_type=0, uploaded_by="hr1")

    p1_candidates = repo.list_by_position(pos1.id)
    assert len(p1_candidates) == 2


# ===== Interview 测试 =====

def test_interview_create_with_defaults(db: Session):
    """Interview 创建（自动生成 token + langgraph_thread_id）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )

    repo = InterviewRepository(db)
    interview = repo.create(
        candidate_id=cand.id,
        position_id=pos.id,
        start_time=1719748800,
        interviewer="技术总监",
    )
    assert interview.id is not None
    assert interview.status == 0  # 默认未开始
    assert interview.token is not None
    assert len(interview.token) == 32  # 默认 32 位
    assert interview.langgraph_thread_id is not None
    # UUID 长度 36（含 4 个连字符）
    assert len(interview.langgraph_thread_id) == 36
    assert interview.answered_count == 0


def test_interview_get_by_token(db: Session):
    """按 token 查面试（§14.7 候选人鉴权用）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    found = InterviewRepository(db).get_by_token(interview.token)
    assert found is not None
    assert found.id == interview.id
    assert found.token == interview.token


def test_interview_update_status(db: Session):
    """状态机更新（0→1→2→3→4）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    # 0 → 1（试题已备好）
    InterviewRepository(db).update_status(interview.id, 1)
    assert InterviewRepository(db).get(interview.id).status == 1

    # 1 → 2（进行中）
    InterviewRepository(db).update_status(interview.id, 2)
    assert InterviewRepository(db).get(interview.id).status == 2

    # 2 → 3（完毕）应该同时记录 end_time
    InterviewRepository(db).update_status(interview.id, 3)
    updated = InterviewRepository(db).get(interview.id)
    assert updated.status == 3
    assert updated.end_time is not None


def test_interview_update_questions_generated(db: Session):
    """节点 A 出题完成后更新（§10.4）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    InterviewRepository(db).update_questions_generated(
        interview.id,
        question_count=10,
        difficulty_distribution={"hard": 3, "medium": 5, "easy": 2},
    )

    updated = InterviewRepository(db).get(interview.id)
    assert updated.status == 1
    assert updated.question_count == 10
    assert updated.total_hard_questions == 3
    assert updated.total_medium_questions == 5
    assert updated.total_easy_questions == 2


def test_interview_increment_answered_to_completion(db: Session):
    """逐题答题 + 自动状态完成（§10.6）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )
    InterviewRepository(db).update_questions_generated(
        interview.id, question_count=3, difficulty_distribution={"hard": 0, "medium": 3, "easy": 0}
    )

    # 答完 2 题（应保持 status=2）
    InterviewRepository(db).increment_answered(interview.id)
    InterviewRepository(db).increment_answered(interview.id)
    assert InterviewRepository(db).get(interview.id).status == 2
    assert InterviewRepository(db).get(interview.id).answered_count == 2

    # 答完第 3 题（应自动变 status=3）
    InterviewRepository(db).increment_answered(interview.id)
    updated = InterviewRepository(db).get(interview.id)
    assert updated.status == 3
    assert updated.answered_count == 3
    assert updated.end_time is not None


def test_interview_update_report(db: Session):
    """报告生成完成后更新（§10.4 节点 D）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    InterviewRepository(db).update_report(
        interview.id,
        report_path="/app/storage/reports/1.pdf",
        is_passed=1,
    )

    updated = InterviewRepository(db).get(interview.id)
    assert updated.status == 4
    assert updated.report_path == "/app/storage/reports/1.pdf"
    assert updated.is_passed == 1


def test_interview_list_by_status_for_stuck_check(db: Session):
    """卡住巡检用（§10.7）"""
    from datetime import datetime, timedelta

    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )
    # 推进到 status=1（试题已备好），否则卡住检查查不到
    InterviewRepository(db).update_status(interview.id, 1)

    # 手动把 updated_at 改成 90 分钟前，模拟"卡住的面试"
    interview.updated_at = int((datetime.utcnow() - timedelta(minutes=90)).timestamp())
    db.commit()

    # 60 分钟阈值：90 分钟前的记录算卡住（older than 60 min）
    stuck = InterviewRepository(db).list_by_status(statuses=[1, 2, 3], older_than_minutes=60)
    assert len(stuck) == 1

    # 120 分钟阈值：90 分钟前的记录不算卡住（90 < 120，不够 old）
    not_stuck = InterviewRepository(db).list_by_status(statuses=[1, 2, 3], older_than_minutes=120)
    assert len(not_stuck) == 0

    # 5 分钟阈值：90 分钟前的记录算卡住
    very_stuck = InterviewRepository(db).list_by_status(statuses=[1, 2, 3], older_than_minutes=5)
    assert len(very_stuck) == 1

    # 无时间过滤：所有 status=1/2/3 的都返回
    all_status = InterviewRepository(db).list_by_status(statuses=[1, 2, 3])
    assert len(all_status) == 1


def test_interview_list_by_status_no_time_filter(db: Session):
    """无时间过滤时返回所有匹配状态的面试"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )
    InterviewRepository(db).update_status(interview.id, 1)
    InterviewRepository(db).update_status(interview.id, 2)

    # 不传 older_than_minutes
    in_progress = InterviewRepository(db).list_by_status(statuses=[2])
    assert len(in_progress) == 1
    assert in_progress[0].status == 2


# ===== InterviewQuestion 测试 =====

def test_question_bulk_create(db: Session):
    """批量创建题目（§10.4 节点 A 出题）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    repo = InterviewQuestionRepository(db)
    questions_data = [
        {"question": f"Q{i}", "score_standard": f"S{i}", "difficulty": "hard" if i < 3 else "easy"}
        for i in range(1, 11)
    ]
    questions = repo.bulk_create(interview.id, questions_data)

    assert len(questions) == 10
    assert repo.count_by_interview(interview.id) == 10
    assert repo.count_answered(interview.id) == 0


def test_question_update_answer(db: Session):
    """提交答案（§10.6）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )
    repo = InterviewQuestionRepository(db)
    q = repo.create(interview_id=interview.id, question="Q1", difficulty="medium")

    # 提交答案
    updated = repo.update_answer(
        q.id,
        answer_text="候选人的回答文本",
        answer_audio_path="/path/to/audio.webm",
    )
    assert updated.answer_text == "候选人的回答文本"
    assert updated.answered_at is not None

    # 统计
    assert repo.count_answered(interview.id) == 1
    unanswered = repo.list_unanswered(interview.id)
    assert len(unanswered) == 0


# ===== AuditLog 测试 =====

def test_audit_log_create_and_metadata(db: Session):
    """审计日志创建 + metadata 解析"""
    repo = AuditLogRepository(db)
    log = repo.create(
        event_type="interview_created",
        actor_id="admin",
        actor_type="user",
        interview_id=42,
        metadata={"position_id": 1, "candidate_id": "cand-1", "extra": {"key": "value"}},
    )
    assert log.event_type == "interview_created"
    assert log.metadata_dict["position_id"] == 1
    assert log.metadata_dict["extra"]["key"] == "value"


def test_audit_log_idempotent(db: Session):
    """幂等性查询（§3 决策 #3）"""
    repo = AuditLogRepository(db)
    repo.create(
        event_type="answer_submitted",
        actor_id="candidate-1",
        metadata={"idempotency_key": "key-123"},
    )

    # 重复查询应能找到
    found = repo.find_idempotent("answer_submitted", "candidate-1", "key-123")
    assert found is not None

    # 不存在的 key
    not_found = repo.find_idempotent("answer_submitted", "candidate-1", "key-999")
    assert not_found is None


def test_audit_log_list_by_interview(db: Session):
    """按面试查审计日志（HR 后台展示用）"""
    repo = AuditLogRepository(db)
    repo.create(event_type="interview_created", interview_id=42)
    repo.create(event_type="questions_generated", interview_id=42)
    repo.create(event_type="interview_created", interview_id=43)

    logs_42 = repo.list_by_interview(42)
    assert len(logs_42) == 2
    assert all(log.interview_id == 42 for log in logs_42)


# ===== 关系测试 =====

def test_candidate_foreign_key_to_position(db: Session):
    """Candidate.position_id 外键约束"""
    from sqlalchemy.exc import IntegrityError

    repo = CandidateRepository(db)
    # 不存在的 position_id 应该报错
    with pytest.raises(IntegrityError):
        repo.create(
            id="c1",
            position_id=9999,  # 不存在
            name="X",
            email="x@x.com",
            resume_type=0,
            uploaded_by="hr1",
        )
        db.commit()


def test_interview_foreign_keys(db: Session):
    """Interview 外键约束（candidate + position）"""
    from sqlalchemy.exc import IntegrityError

    # 不存在的 candidate_id
    pos = PositionRepository(db).create(name="P1")
    repo = InterviewRepository(db)
    with pytest.raises(IntegrityError):
        repo.create(
            candidate_id="nonexistent",
            position_id=pos.id,
            start_time=1,
        )
        db.commit()


def test_cascade_delete_interview_questions(db: Session):
    """删除面试时级联删除题目（手动级联）"""
    pos = PositionRepository(db).create(name="P1")
    cand = CandidateRepository(db).create(
        id="c1", position_id=pos.id, name="李四", email="li@x.com",
        resume_type=0, uploaded_by="hr1",
    )
    interview = InterviewRepository(db).create(
        candidate_id=cand.id, position_id=pos.id, start_time=1,
    )

    q_repo = InterviewQuestionRepository(db)
    q_repo.bulk_create(interview.id, [{"question": "Q1"}, {"question": "Q2"}])
    assert q_repo.count_by_interview(interview.id) == 2

    # 删除面试 + 手动删除题目（外键未配置 cascade）
    deleted_count = q_repo.delete_by_interview(interview.id)
    assert deleted_count == 2
    InterviewRepository(db).delete(interview.id)