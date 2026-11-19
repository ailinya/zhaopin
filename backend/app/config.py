"""
应用配置（pydantic-settings）

从 .env 文件或环境变量加载所有配置项。
**优先级：init 参数 > .env 文件 > 环境变量 > 字段默认值**

pydantic-settings 默认是「环境变量 > .env」，会把 shell 里残留的旧值覆盖 .env。
我们反序：让 .env 胜出，避免 shell 环境变量偷偷改线上配置。
"""
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource


class Settings(BaseSettings):
    """应用配置"""

    # ===== 基础 =====
    ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    API_PORT: int = 8000

    # ===== LLM =====
    LLM_PROVIDER: Literal["deepseek", "qwen", "glm"] = "deepseek"
    OPENAI_API_KEY: str = "sk-placeholder-replace-me"
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 3

    # ===== 数据库 =====
    DATABASE_URL: str = "sqlite:///./interview.db"
    DB_ECHO: bool = False  # 是否打印 SQL

    # ===== 文件存储 =====
    STORAGE_PATH: str = "./storage"
    MAX_FILE_SIZE_MB: int = 50

    # ===== JWT =====
    JWT_SECRET_KEY: str = "change-me-to-strong-random-string-min-32-bytes"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ===== CORS =====
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
    ]

    # ===== 候选人 Token =====
    CANDIDATE_TOKEN_LENGTH: int = 32

    # ===== Whisper =====
    WHISPER_MODEL: Literal["tiny", "base", "small", "medium", "large-v3"] = "base"
    WHISPER_DEVICE: Literal["auto", "cpu", "cuda"] = "auto"
    WHISPER_TIMEOUT_SECONDS: int = 300  # 5 分钟

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """重写优先级：init > .env > env > secret

        默认顺序是 init > env > dotenv > secret，shell 环境变量会盖掉 .env。
        这里交换 env 和 dotenv 的顺序，让 .env 文件胜出。
        """
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)


# 全局单例
settings = Settings()


def get_storage_path() -> Path:
    """获取存储目录（绝对路径）"""
    return Path(settings.STORAGE_PATH).resolve()