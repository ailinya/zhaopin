"""
结构化日志（structlog → JSON）

所有日志输出为 JSON 格式，便于：
- 日志聚合（ELK / Loki）
- 按字段检索（request_id / interview_id / user_id 等）
- 监控告警（按 event 名称）

使用示例：
    from app.core.logging import get_logger
    logger = get_logger(__name__)

    logger.info("interview_created", interview_id=42, candidate_id=123)
    # 输出: {"event":"interview_created","interview_id":42,...,"level":"info","timestamp":"..."}
"""
import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """
    配置 structlog 输出 JSON 到 stderr

    Args:
        level: 日志级别（DEBUG / INFO / WARNING / ERROR）
    """
    # 解析日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 配置标准 logging（structlog 基于它）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            # 添加日志级别
            structlog.stdlib.add_log_level,
            # 添加 ISO 时间戳
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # 异常堆栈渲染
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # 输出为 JSON
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取 logger（按模块名）"""
    return structlog.get_logger(name)