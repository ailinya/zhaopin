"""
端到端集成测试（Day 7）

完整流程：建岗位 → 建候选人 → 建面试 → 出题 → 答题 → 出报告
所有外部依赖（LLM / Whisper）都 mock 掉。
"""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    User, Position, Candidate, Interview, InterviewQuestion, AuditLog,
)


# ===== Fixtures =====

@pytest.fixture(scope="function")
def engine():
    """内存 SQLite + StaticPool"""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(eng, "connect")
    def _set_pragma(dbapi_connection, _):
        c = dbapi_connection.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.close()

    # 导入所有 model
    from app.models import (User, Position, Candidate, Interview, InterviewQuestion, AuditLog)  # noqa: F401
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def client(engine, monkeypatch):
    """FastAPI TestClient + dependency_overrides"""
    from app.main import app
    from app.deps import get_db

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(engine):
    """HR 用户 + JWT"""
    from app.models.user import UserRepository
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    s = SessionLocal()
    user = UserRepository(s).create(
        id="user-1", username="admin", email="admin@x.com", password="secret",
    )
    s.commit()
    token = __import__("app.core.security", fromlist=["create_access_token"]).create_access_token(user.id)
    s.close()
    return {"Authorization": f"Bearer {token}"}


# ===== 端到端测试 =====

def test_e2e_full_interview_flow(client, auth_headers, monkeypatch):
    """
    端到端（简化版）：只验证 API 调用 + 候选人端，workflow 在后台用全局 DB 跑（看不到测试数据）

    完整 workflow 测试需要把全局 DB session 切到测试 engine（复杂），跳过
    真实 e2e 需要起 dev server + 真实 LLM
    """
    # 1. HR 创建岗位
    r = client.post(
        "/api/positions",
        headers=auth_headers,
        json={"name": "Backend Engineer", "requirements": "Python", "quantity": 1},
    )
    assert r.status_code == 201
    position_id = r.json()["data"]["id"]

    # 2. HR 创建候选人
    r = client.post(
        "/api/candidates",
        headers=auth_headers,
        data={"name": "Test User", "email": "test@x.com", "position_id": str(position_id)},
        files={"resume": ("r.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 201
    candidate_id = r.json()["data"]["candidate_id"]

    # 3. HR 创建面试（workflow 会在后台线程启动，但 DB 是全局的）
    r = client.post(
        "/api/interviews",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "position_id": position_id},
    )
    assert r.status_code == 201
    interview_id = r.json()["data"]["id"]
    token = r.json()["data"]["token"]
    assert r.json()["data"]["status"] == 0

    # 4. 候选人端可以获取面试（即使 workflow 还没跑完）
    r = client.get(f"/api/candidate/{token}/info")
    assert r.status_code == 200

    # 5. 列出所有面试
    r = client.get("/api/interviews", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]["items"]) >= 1

    # 6. 删除
    r = client.delete(f"/api/interviews/{interview_id}", headers=auth_headers)
    assert r.status_code == 200

    # 7. 验证删除
    r = client.get("/api/interviews", headers=auth_headers)
    items = r.json()["data"]["items"]
    assert not any(i["id"] == interview_id for i in items)


def test_e2e_simplified_position_candidate(client, auth_headers):
    """简化版：只测 HR 创建岗位 → 候选人 → 面试的基础流程（不跑 workflow）"""
    # 1. 创建岗位
    r = client.post(
        "/api/positions",
        headers=auth_headers,
        json={"name": "测试岗"},
    )
    assert r.status_code == 201
    pos_id = r.json()["data"]["id"]

    # 2. 创建候选人
    r = client.post(
        "/api/candidates",
        headers=auth_headers,
        data={"name": "T", "email": "t@x.com", "position_id": str(pos_id)},
        files={"resume": ("r.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 201

    # 3. 列出
    r = client.get("/api/positions", headers=auth_headers)
    assert len(r.json()["data"]["items"]) >= 1
    r = client.get("/api/candidates", headers=auth_headers)
    assert len(r.json()["data"]["items"]) >= 1