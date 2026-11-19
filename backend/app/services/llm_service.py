"""
LLM 服务（§5 + §16）

封装 OpenAI 兼容 API（DeepSeek / Qwen / GLM）：
- chat()：纯文本对话
- chat_json()：结构化 JSON 输出（带 Pydantic schema 校验）
- 3 次指数退避重试（429 / 5xx）
- Provider 工厂（settings.LLM_PROVIDER 切换）

设计：
- 同步阻塞（OpenAI SDK 不原生 async，用 sync 模式）
- 调用方用 run_in_executor 异步化（asr_service 同款模式）
"""
import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from app.config import settings


logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseModel)


# ===== 客户端单例 =====
_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取 OpenAI 客户端（OpenAI 兼容 API）"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,  # 我们自己实现重试（更细粒度）
        )
    return _client


def _retry_with_backoff(func, *args, max_retries: int = 3, **kwargs):
    """指数退避重试

    触发重试：RateLimitError (429), APIError (5xx), APITimeoutError
    不重试：APIError (4xx 除了 429)
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            last_exception = e
            wait = 2 ** attempt
            logger.warning(
                "llm_rate_limited",
                extra={"attempt": attempt + 1, "wait_seconds": wait},
            )
            time.sleep(wait)
        except APITimeoutError as e:
            last_exception = e
            wait = 2 ** attempt
            logger.warning(
                "llm_timeout",
                extra={"attempt": attempt + 1, "wait_seconds": wait},
            )
            time.sleep(wait)
        except APIError as e:
            # 5xx 重试，4xx 直接抛
            if e.status_code and 500 <= e.status_code < 600:
                last_exception = e
                wait = 2 ** attempt
                logger.warning(
                    "llm_server_error",
                    extra={"status": e.status_code, "attempt": attempt + 1, "wait": wait},
                )
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            # 其他异常直接抛（不重试）
            raise

    raise last_exception


# ===== Chat API =====

def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
) -> str:
    """
    纯文本对话

    Args:
        messages: [{"role": "system", "content": "..."}, ...]
        model: 模型名（默认 settings.LLM_MODEL）
        temperature: 温度（默认 settings.LLM_TEMPERATURE）

    Returns:
        助手回复文本
    """
    client = get_client()
    model = model or settings.LLM_MODEL
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
    max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES

    def _call():
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content

    result = _retry_with_backoff(_call, max_retries=max_retries)
    logger.info("llm_chat_success", extra={"model": model})
    return result


def _generate_mock_questions(schema: type[T]) -> T:
    """开发模式：生成模拟题目（当没有 API Key 时使用）"""
    from pydantic import create_model

    # 根据 schema 类型生成模拟数据
    schema_name = schema.__name__

    if schema_name == "QuestionList":
        # 生成 10 道模拟面试题
        mock_questions = [
            {"question": "请介绍一下你的工作经历和项目经验？", "difficulty": "medium", "score_standard": "根据回答完整度和相关性评分"},
            {"question": "请详细说明你为什么对这个岗位感兴趣？", "difficulty": "easy", "score_standard": "根据表达清晰度和热情度评分"},
            {"question": "请描述一次你在团队中解决冲突的经历？", "difficulty": "medium", "score_standard": "根据问题解决能力和沟通技巧评分"},
            {"question": "请说明你的职业规划是什么？", "difficulty": "easy", "score_standard": "根据目标清晰度和可行性评分"},
            {"question": "请介绍一个你最成功的项目案例？", "difficulty": "medium", "score_standard": "根据项目影响力和个人贡献度评分"},
            {"question": "请说明你的优势和改进空间？", "difficulty": "easy", "score_standard": "根据自我认知深度评分"},
            {"question": "请描述你如何处理工作压力？", "difficulty": "easy", "score_standard": "根据应对策略合理性评分"},
            {"question": "请说明你为什么离开上一家公司？", "difficulty": "medium", "score_standard": "根据表达方式成熟度评分"},
            {"question": "请介绍你对这个行业的看法？", "difficulty": "hard", "score_standard": "根据行业洞察深度评分"},
            {"question": "请说明你的期望薪资和到岗时间？", "difficulty": "easy", "score_standard": "根据合理性和灵活性评分"},
        ]
        return schema(questions=mock_questions)

    # 其他 schema 类型抛出异常
    raise ValueError(f"Mock mode not supported for schema: {schema_name}")


def chat_json(
    messages: list[dict],
    schema: type[T],
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
) -> T:
    """
    结构化 JSON 输出（带 Pydantic schema 校验）

    Args:
        messages: 消息列表
        schema: Pydantic 模型类（用于校验输出）
        model: 模型名
        temperature: 温度

    Returns:
        schema 的实例（已校验）

    Raises:
        ValidationError: LLM 输出不符合 schema
    """
    # 开发模式：如果 API key 是 placeholder，使用 mock 数据
    if settings.OPENAI_API_KEY == "sk-placeholder-replace-me":
        logger.warning("llm_using_mock mode (no API key configured)")
        return _generate_mock_questions(schema)

    client = get_client()
    model = model or settings.LLM_MODEL
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
    max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES

    def _call():
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},  # 强制 JSON 输出
        )
        return response.choices[0].message.content

    raw_text = _retry_with_backoff(_call, max_retries=max_retries)

    # 解析 JSON
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        # 尝试提取 ```json ... ``` 块
        cleaned = _extract_json_block(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("llm_json_decode_failed", extra={"raw": raw_text[:500]})
            raise

    # Pydantic schema 校验
    try:
        instance = schema.model_validate(data)
    except ValidationError as e:
        logger.error(
            "llm_schema_validation_failed",
            extra={"schema": schema.__name__, "errors": str(e)},
        )
        raise

    logger.info("llm_chat_json_success", extra={"model": model, "schema": schema.__name__})
    return instance


def _extract_json_block(text: str) -> str:
    """从 LLM 输出中提取 ```json ... ``` 块"""
    if "```json" in text:
        start = text.find("```json") + len("```json")
        end = text.find("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + len("```")
        end = text.find("```", start)
        return text[start:end].strip()
    return text.strip()