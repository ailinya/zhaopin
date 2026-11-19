"""
简单 i18n 工具（Day 4）

支持中英文切换：
- t(key, lang='zh') 返回翻译字符串
- fallback：未翻译时返回 key 本身 + warning
- 字符串文件：i18n/zh.json / i18n/en.json

Week 5+ 增强：
- 支持占位符 {name}
- 按 Accept-Language 自动选语言
- 前端 i18next 集成
"""
import json
import logging
from pathlib import Path
from typing import Literal


logger = logging.getLogger(__name__)


# ===== 字符串文件 =====
_I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
_supported_languages = ("zh", "en")
_default_language: Literal["zh", "en"] = "zh"

_translations: dict[str, dict[str, str]] = {}


def _load_translations() -> None:
    """从 JSON 文件加载所有语言的翻译"""
    global _translations
    for lang in _supported_languages:
        path = _I18N_DIR / f"{lang}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        else:
            logger.warning(f"i18n_file_missing path={path}")
            _translations[lang] = {}


# 启动时加载
_load_translations()


def t(key: str, lang: str = _default_language, **kwargs) -> str:
    """
    翻译 key 为指定语言的字符串

    Args:
        key: 翻译键（支持嵌套，用 . 分隔，如 "errors.not_found"）
        lang: 语言（zh / en）
        **kwargs: 模板变量（用 {var} 占位）

    Examples:
        t("common.welcome")                  # → "欢迎"
        t("common.welcome", lang="en")       # → "Welcome"
        t("user.greeting", name="张三")       # → "你好，张三"
    """
    if lang not in _translations:
        logger.warning(f"i18n_unsupported_lang lang={lang}")
        lang = _default_language

    # 支持嵌套 key（"a.b.c"）
    text = _translations[lang]
    for part in key.split("."):
        if isinstance(text, dict) and part in text:
            text = text[part]
        else:
            # 找不到：fallback 到英文，最后 fallback 到 key
            if lang != "en" and "en" in _translations:
                text = _translations["en"]
                for fallback_part in key.split("."):
                    if isinstance(text, dict) and fallback_part in text:
                        text = text[fallback_part]
                    else:
                        logger.warning(f"i18n_key_missing key={key} lang={lang}")
                        return key
                break
            else:
                logger.warning(f"i18n_key_missing key={key} lang={lang}")
                return key

    if not isinstance(text, str):
        logger.warning(f"i18n_key_not_string key={key}")
        return key

    # 模板变量替换
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"i18n_format_error key={key} missing={e}")
            return text

    return text


def set_default_language(lang: Literal["zh", "en"]) -> None:
    """设置默认语言（Week 5+ 按用户偏好动态设置）"""
    global _default_language
    if lang in _supported_languages:
        _default_language = lang
    else:
        logger.warning(f"i18n_unsupported_default_lang lang={lang}")


def get_default_language() -> str:
    """获取默认语言"""
    return _default_language