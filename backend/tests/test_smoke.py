"""
烟雾测试

启动后跑 pytest 验证：
- 应用能导入
- 配置能加载
- 基础 schema 能实例化
- /healthz 端点返回 200
"""
import pytest
from fastapi.testclient import TestClient


def test_import_app():
    """应用可导入"""
    from app.main import app
    assert app is not None
    assert app.title == "AI 智能面试系统 API"


def test_config_loads():
    """配置可加载"""
    from app.config import settings
    assert settings.ENV in ["development", "staging", "production"]
    assert settings.API_PORT == 8000


def test_api_response_ok():
    """APIResponse.ok 工厂方法"""
    from app.schemas.response import APIResponse

    resp = APIResponse.ok({"foo": "bar"})
    assert resp.code == 0
    assert resp.msg == "success"
    assert resp.data == {"foo": "bar"}
    assert resp.is_success is True


def test_api_response_err():
    """APIResponse.err 工厂方法"""
    from app.schemas.response import APIResponse

    resp = APIResponse.err(1001, "参数缺失")
    assert resp.code == 1001
    assert resp.msg == "参数缺失"
    assert resp.is_success is False


def test_error_code_values():
    """ErrorCode 数值正确（API 契约依赖这些值）"""
    from app.core.errors import ErrorCode

    assert ErrorCode.PARAM_MISSING == 1001
    assert ErrorCode.INTERVIEW_NOT_FOUND == 2003
    assert ErrorCode.RESUME_NOT_PARSED == 3001
    assert ErrorCode.LLM_FAILED == 4010
    assert ErrorCode.INTERNAL_ERROR == 5000


def test_status_code_mapping():
    """错误码 → HTTP 状态码映射"""
    from app.core.errors import ErrorCode, get_status_code

    assert get_status_code(int(ErrorCode.PARAM_MISSING)) == 400
    assert get_status_code(int(ErrorCode.INTERVIEW_NOT_FOUND)) == 404
    assert get_status_code(int(ErrorCode.INVALID_STATE_TRANSITION)) == 409
    assert get_status_code(int(ErrorCode.UNAUTHORIZED)) == 401
    assert get_status_code(int(ErrorCode.LLM_FAILED)) == 502
    assert get_status_code(int(ErrorCode.INTERNAL_ERROR)) == 500


def test_password_hash_and_verify():
    """密码 hash/verify"""
    from app.core.security import hash_password, verify_password

    plain = "my-secret-password-123"
    hashed = hash_password(plain)

    assert hashed != plain  # hash 不能等于明文
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_roundtrip():
    """JWT 签发 + 解码 roundtrip"""
    from app.core.security import (
        create_access_token,
        create_refresh_token,
        decode_token,
    )

    user_id = "user-123"
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)

    # access 解码
    payload = decode_token(access, expected_type="access")
    assert payload["sub"] == user_id
    assert payload["type"] == "access"

    # refresh 解码
    payload = decode_token(refresh, expected_type="refresh")
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"

    # 类型不匹配抛错
    import jwt

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(access, expected_type="refresh")


def test_candidate_token_generation():
    """候选人 token 生成"""
    from app.core.security import generate_candidate_token

    token = generate_candidate_token(32)
    assert len(token) == 32
    assert token.isalnum()  # 只含字母数字

    # 两次生成不应相同
    token2 = generate_candidate_token(32)
    assert token != token2


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    from app.main import app
    return TestClient(app)


def test_healthz(client):
    """存活检查端点"""
    response = client.get("/healthz")
    assert response.status_code == 200

    body = response.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"


def test_readyz(client):
    """就绪检查端点"""
    response = client.get("/readyz")
    assert response.status_code == 200

    body = response.json()
    assert "checks" in body["data"]
    # DB 可能未初始化，但响应结构应该是对的
    assert "db" in body["data"]["checks"]
    assert "storage" in body["data"]["checks"]