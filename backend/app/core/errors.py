"""
错误码体系（§16.2 借鉴 GraphRAGAgent）

错误码分段：
- 1001-1999: 参数/校验
- 2001-2999: 资源未找到
- 3001-3999: 业务逻辑
- 4001-4999: 外部服务/鉴权
- 5000:     内部错误

APIError 是 FastAPI HTTPException 的子类，会被 main.py 的全局 handler
捕获并自动包装为 APIResponse[T] 响应。
"""
from enum import IntEnum

from fastapi import HTTPException


class ErrorCode(IntEnum):
    """业务错误码"""

    # ===== 1001-1999: 参数/校验 =====
    PARAM_MISSING = 1001            # 缺少必填参数
    PARAM_TYPE_ERROR = 1002         # 参数类型错误
    PARAM_FORMAT_ERROR = 1003       # 参数格式错误（如 email 格式不对）
    PARAM_OUT_OF_RANGE = 1004      # 参数超出范围

    # ===== 2001-2999: 资源未找到 =====
    POSITION_NOT_FOUND = 2001
    CANDIDATE_NOT_FOUND = 2002
    INTERVIEW_NOT_FOUND = 2003
    QUESTION_NOT_FOUND = 2004
    RESUME_NOT_FOUND = 2005
    REPORT_NOT_FOUND = 2006
    USER_NOT_FOUND = 2007

    # ===== 3001-3999: 业务逻辑 =====
    RESUME_NOT_PARSED = 3001       # 简历还在解析中
    INTERVIEW_ALREADY_COMPLETED = 3002  # 面试已完成
    INVALID_STATE_TRANSITION = 3003     # 状态机非法跃迁
    DUPLICATE_TRIGGER = 3004            # 重复触发（如多次 resume）
    RESUME_SCANNED = 3005               # 简历是扫描件
    QUESTION_NOT_READY = 3006           # 题目未生成
    RESUME_RETRY_NOT_AVAILABLE = 3007   # 简历无法重试（无原始字节）

    # ===== 4001-4999: 外部服务/鉴权 =====
    UNAUTHORIZED = 4001            # 未登录
    TOKEN_EXPIRED = 4002           # Token 过期
    FORBIDDEN = 4003               # 权限不足
    INVALID_CREDENTIALS = 4004     # 用户名密码错误
    USER_DISABLED = 4005           # 用户已停用
    LLM_FAILED = 4010              # LLM 调用失败
    WHISPER_FAILED = 4011          # Whisper 转写失败
    WEASYPRINT_FAILED = 4012       # PDF 渲染失败
    FILE_STORAGE_FAILED = 4013     # 文件存储失败
    UNSUPPORTED_FILE_TYPE = 4014   # 不支持的文件类型
    FILE_TOO_LARGE = 4015          # 文件过大
    CORRUPT_FILE = 4016            # 文件损坏
    ENCRYPTED_PDF = 4017           # PDF 已加密
    IDEMPOTENT_DUPLICATE = 4018    # 幂等性重复请求

    # ===== 5000: 内部 =====
    INTERNAL_ERROR = 5000


# ===== HTTP 状态码映射 =====
_STATUS_CODE_MAP = {
    # 4xx: 客户端错误
    **{code: 400 for code in range(1001, 2000)},
    **{code: 404 for code in range(2001, 3000)},
    **{code: 409 for code in range(3001, 4000)},  # 业务冲突
    4001: 401,
    4002: 401,
    4003: 403,
    4004: 401,
    4005: 403,
    4018: 409,  # 幂等冲突
    4014: 415,  # Unsupported Media Type
    4015: 413,  # Payload Too Large
    # 5xx: 服务器错误
    4010: 502,  # LLM 服务异常
    4011: 502,
    4012: 500,
    4013: 500,
    5000: 500,
}


def get_status_code(error_code: int) -> int:
    """根据错误码获取 HTTP 状态码"""
    return _STATUS_CODE_MAP.get(error_code, 500)


# ===== APIError =====
class APIError(HTTPException):
    """
    业务异常

    使用示例：
        if not interview:
            raise APIError.not_found(ErrorCode.INTERVIEW_NOT_FOUND, f"面试 {id} 不存在")

        if not user:
            raise APIError.unauthorized(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误")
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int | None = None,
        data: dict | None = None,
    ):
        if status_code is None:
            status_code = get_status_code(int(code))
        super().__init__(
            status_code=status_code,
            detail={
                "code": int(code),
                "msg": message,
                "data": data or {},
            },
        )

    # ===== 工厂方法 =====

    @classmethod
    def bad_request(
        cls,
        code: ErrorCode = ErrorCode.PARAM_MISSING,
        msg: str = "请求参数错误",
        data: dict | None = None,
    ) -> "APIError":
        return cls(code, msg, status_code=400, data=data)

    @classmethod
    def not_found(
        cls,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        msg: str = "资源不存在",
    ) -> "APIError":
        return cls(code, msg, status_code=404)

    @classmethod
    def conflict(
        cls,
        code: ErrorCode,
        msg: str,
        data: dict | None = None,
    ) -> "APIError":
        return cls(code, msg, status_code=409, data=data)

    @classmethod
    def unauthorized(
        cls,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        msg: str = "未授权",
    ) -> "APIError":
        return cls(code, msg, status_code=401)

    @classmethod
    def forbidden(
        cls,
        code: ErrorCode = ErrorCode.FORBIDDEN,
        msg: str = "权限不足",
    ) -> "APIError":
        return cls(code, msg, status_code=403)

    @classmethod
    def internal(
        cls,
        msg: str = "服务器内部错误",
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    ) -> "APIError":
        return cls(code, msg, status_code=500)