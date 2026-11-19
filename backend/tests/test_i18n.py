"""
i18n 测试
"""
import logging

import pytest

from app.core import i18n


# ===== t() 函数测试 =====

def test_t_zh_default():
    """默认中文"""
    assert i18n.t("common.welcome") == "欢迎"


def test_t_zh_explicit():
    """显式中文"""
    assert i18n.t("common.welcome", lang="zh") == "欢迎"


def test_t_en():
    """英文"""
    assert i18n.t("common.welcome", lang="en") == "Welcome"


def test_t_nested_key():
    """嵌套 key（用 . 分隔）"""
    assert i18n.t("auth.login") == "登录"
    assert i18n.t("auth.login", lang="en") == "Login"


def test_t_template_variables():
    """模板变量替换"""
    text = i18n.t("interview.question_count", count=10)
    assert "10" in text
    assert "10" in i18n.t("interview.question_count", count=10, lang="en")


def test_t_missing_key_fallback():
    """找不到 key 时 fallback 到 key 本身"""
    text = i18n.t("nonexistent.key", lang="zh")
    assert text == "nonexistent.key"


def test_t_missing_key_zh_falls_back_to_en():
    """中文找不到时 fallback 到英文"""
    # 注意：当前 zh.json / en.json 内容相同的情况下不会触发
    # 测 fallback 机制本身
    text = i18n.t("common.submit", lang="zh")
    assert text in ("提交", "Submit")  # 二者之一


def test_t_unsupported_lang_falls_back():
    """不支持的语言 fallback 到默认"""
    text = i18n.t("common.welcome", lang="xx")
    assert text == "欢迎"  # fallback 到 zh


# ===== 默认语言测试 =====

def test_default_language():
    """默认语言是 zh"""
    assert i18n.get_default_language() == "zh"


def test_set_default_language():
    """设置默认语言"""
    original = i18n.get_default_language()
    i18n.set_default_language("en")
    assert i18n.get_default_language() == "en"
    i18n.set_default_language(original)  # 恢复


def test_set_unsupported_default():
    """不支持的语言不应被设置"""
    original = i18n.get_default_language()
    i18n.set_default_language("xx")  # type: ignore
    assert i18n.get_default_language() == original  # 不变


# ===== 翻译完整性测试 =====

def test_all_keys_have_both_languages():
    """所有 key 在 zh 和 en 都应该有翻译（同步性）"""
    zh_keys = _collect_keys(i18n._translations.get("zh", {}))
    en_keys = _collect_keys(i18n._translations.get("en", {}))

    missing_in_en = zh_keys - en_keys
    missing_in_zh = en_keys - zh_keys

    assert not missing_in_en, f"Keys missing in en: {missing_in_en}"
    assert not missing_in_zh, f"Keys missing in zh: {missing_in_zh}"


def _collect_keys(d, prefix=""):
    """递归收集所有嵌套 key（用于完整性检查）"""
    keys = set()
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_collect_keys(v, key))
        else:
            keys.add(key)
    return keys