"""
邮件服务测试
"""
import logging
from unittest.mock import patch, MagicMock

import pytest

from app.services.email_service import send_email, send_interview_invite, send_report_ready


@pytest.fixture
def caplog(caplog):
    caplog.set_level(logging.INFO)
    return caplog


# ===== send_email 测试 =====

def test_send_email_console_backend(caplog):
    """console backend：邮件打到日志（开发模式）"""
    result = send_email(
        to="test@example.com",
        subject="Test Subject",
        template_name="interview_invite.html",
        context={"candidate_name": "张三", "position_name": "工程师", "interview_url": "http://x", "interview_time": "今天"},
        backend="console",
    )
    assert result is True
    # 检查日志
    assert any("email_console" in r.message for r in caplog.records)


def test_send_email_renders_template(caplog):
    """模板正确渲染（变量替换）"""
    with caplog.at_level(logging.INFO):
        send_email(
            to="t@x.com",
            subject="s",
            template_name="interview_invite.html",
            context={
                "candidate_name": "Alice",
                "position_name": "Backend",
                "interview_url": "http://test",
                "interview_time": "今天 10:00",
            },
            backend="console",
        )
    # 检查渲染的 HTML 含 Alice
    log_text = " ".join(r.message for r in caplog.records)
    assert "Alice" in log_text


def test_send_email_unknown_backend():
    """未知 backend 返回 False"""
    result = send_email(
        to="t@x.com",
        subject="s",
        template_name="interview_invite.html",
        context={},
        backend="unknown_backend",  # type: ignore
    )
    assert result is False


def test_send_interview_invite(caplog):
    """便捷函数：面试邀请"""
    with caplog.at_level(logging.INFO):
        result = send_interview_invite(
            to_email="candidate@x.com",
            candidate_name="张三",
            position_name="后端工程师",
            interview_url="http://localhost:5173/candidate-portal?token=xxx",
            interview_time="明天 14:00",
        )
    assert result is True
    log_text = " ".join(r.message for r in caplog.records)
    assert "张三" in log_text
    assert "后端工程师" in log_text


def test_send_report_ready_passed(caplog):
    """便捷函数：报告完成（通过）"""
    with caplog.at_level(logging.INFO):
        result = send_report_ready(
            to_email="candidate@x.com",
            candidate_name="李四",
            position_name="前端工程师",
            overall_score=85,
            report_url="http://x.com/report/1",
            is_passed=True,
        )
    assert result is True
    log_text = " ".join(r.message for r in caplog.records)
    assert "推荐录用" in log_text
    assert "85" in log_text


def test_send_report_ready_failed(caplog):
    """便捷函数：报告完成（未通过）"""
    with caplog.at_level(logging.INFO):
        result = send_report_ready(
            to_email="candidate@x.com",
            candidate_name="王五",
            position_name="后端工程师",
            overall_score=45,
            report_url="http://x.com/report/1",
            is_passed=False,
        )
    assert result is True
    log_text = " ".join(r.message for r in caplog.records)
    assert "暂未通过" in log_text