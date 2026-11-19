"""
邮件服务（Day 4）

支持两种 backend：
- console：开发模式，邮件内容打到日志（生产前必换 SMTP）
- smtp：生产模式，真实 SMTP 发送

用法：
    email_service.send_email(
        to="user@example.com",
        subject="面试邀请",
        template_name="interview_invite.html",
        context={"candidate_name": "张三", "link": "..."}
    )

Week 5+ 增强：
- 邮件模板用 Jinja2 渲染（i18n 支持）
- 异步发送（不影响 API 响应）
- 失败重试
- 死信队列
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings


logger = logging.getLogger(__name__)


# ===== Jinja2 模板 =====
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_template(template_name: str, context: dict) -> str:
    """渲染邮件 HTML 模板"""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


# ===== 主函数 =====

def send_email(
    to: str,
    subject: str,
    template_name: str,
    context: dict,
    backend: Literal["console", "smtp"] | None = None,
) -> bool:
    """
    发送邮件

    Args:
        to: 收件人邮箱
        subject: 邮件主题
        template_name: 模板文件名（如 "interview_invite.html"）
        context: 模板变量
        backend: 强制指定 backend（默认根据 env 推断）

    Returns:
        是否发送成功
    """
    backend = backend or _get_default_backend()
    html_content = _render_template(template_name, context)

    if backend == "console":
        return _send_console(to, subject, html_content)
    elif backend == "smtp":
        return _send_smtp(to, subject, html_content)
    else:
        logger.error("email_unknown_backend", extra={"backend": backend})
        return False


def _get_default_backend() -> str:
    """根据 settings 推断 backend（Week 5+ 用真实 SMTP_HOST 配置）"""
    # 当前 MVP：总是 console。生产时检查 settings.SMTP_HOST 是否配置
    return "console"


def _send_console(to: str, subject: str, html_content: str) -> bool:
    """Console backend：邮件内容打到日志（开发用）"""
    # 把 HTML 全部内容放到 message 里（方便 caplog 抓取）
    preview = html_content.replace("\n", " ")
    logger.info(
        f"email_console to={to} subject={subject!r} len={len(html_content)} preview={preview!r}",
    )
    # 也打印到 stdout（开发时方便看）
    print(f"\n{'='*60}")
    print(f"📧 EMAIL TO: {to}")
    print(f"📋 SUBJECT: {subject}")
    print(f"{'='*60}")
    print(html_content[:500])
    if len(html_content) > 500:
        print(f"... ({len(html_content) - 500} more chars)")
    print(f"{'='*60}\n")
    return True


def _send_smtp(to: str, subject: str, html_content: str) -> bool:
    """SMTP backend：真实发送（Week 5+ 完善配置）"""
    # TODO Week 5: 从 settings 读 SMTP 配置
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", "noreply@interview-system.local")

    try:
        # 构建 MIME
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # 连接 + 发送
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info("email_sent", extra={"to": to, "subject": subject})
        return True

    except Exception as e:
        logger.error(
            "email_send_failed",
            extra={"to": to, "subject": subject, "error": str(e)},
        )
        return False


import os  # 放在最后避免循环引用


# ===== 便捷函数 =====

def send_interview_invite(
    to_email: str,
    candidate_name: str,
    position_name: str,
    interview_url: str,
    interview_time: str | None = None,
) -> bool:
    """发送面试邀请邮件"""
    return send_email(
        to=to_email,
        subject=f"【面试邀请】{position_name} - {candidate_name}",
        template_name="interview_invite.html",
        context={
            "candidate_name": candidate_name,
            "position_name": position_name,
            "interview_url": interview_url,
            "interview_time": interview_time or "请尽快登录查看",
        },
    )


def send_report_ready(
    to_email: str,
    candidate_name: str,
    position_name: str,
    overall_score: int,
    report_url: str,
    is_passed: bool = True,
) -> bool:
    """发送报告生成完成通知"""
    return send_email(
        to=to_email,
        subject=f"【面试报告】{position_name} - {candidate_name}",
        template_name="report_ready.html",
        context={
            "candidate_name": candidate_name,
            "position_name": position_name,
            "overall_score": overall_score,
            "report_url": report_url,
            "is_passed": is_passed,
            "recommendation": "推荐录用" if is_passed else "暂未通过",
        },
    )