"""
服务测试：LLM（mocked） + FileStorage（真实） + Whisper（skip if no model）
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from app.services.file_storage import LocalFileStorage
from app.services.llm_service import chat, chat_json, _extract_json_block


# ===== FileStorage 测试（真实文件系统）=====

@pytest.fixture
def tmp_storage(tmp_path: Path) -> LocalFileStorage:
    """用 pytest tmp_path 隔离每个测试"""
    storage = LocalFileStorage(root_dir=tmp_path)
    yield storage
    # 不需要清理，tmp_path 自动清理


def test_save_resume_creates_file(tmp_storage):
    """保存简历"""
    content = b"%PDF-1.4 fake content"
    path = tmp_storage.save_resume("cand-1", "pdf", content)
    assert path.exists()
    assert path.read_bytes() == content


def test_save_audio_creates_file(tmp_storage):
    """保存音频"""
    content = b"fake webm audio"
    path = tmp_storage.save_audio(42, 1, content)
    assert path.exists()
    assert path.read_bytes() == content
    assert "42" in str(path)
    assert "1" in str(path)


def test_save_report_creates_file(tmp_storage):
    """保存报告"""
    content = b"%PDF-1.4 report"
    path = tmp_storage.save_report(42, content)
    assert path.exists()
    assert path.read_bytes() == content


def test_save_resume_atomic_write(tmp_storage, tmp_path):
    """原子写入：不应留 .tmp 残留"""
    content = b"test content"
    path = tmp_storage.save_resume("cand-1", "pdf", content)
    # 检查 .tmp 不存在
    tmp_files = list(tmp_path.rglob("*.tmp"))
    assert len(tmp_files) == 0, f"临时文件残留: {tmp_files}"


def test_save_resume_rejects_bad_extension(tmp_storage):
    """拒绝不支持的扩展名"""
    with pytest.raises(ValueError, match="Unsupported"):
        tmp_storage.save_resume("cand-1", "exe", b"x")


def test_save_resume_strips_dot_prefix(tmp_storage):
    """扩展名前缀 . 应被剥掉"""
    path = tmp_storage.save_resume("cand-1", ".pdf", b"x")
    assert path.suffix == ".pdf"


def test_read_and_stream(tmp_storage):
    """读和流"""
    path = tmp_storage.save_resume("c1", "pdf", b"hello")
    assert tmp_storage.read(path) == b"hello"
    stream = tmp_storage.stream(path)
    assert stream.read() == b"hello"
    stream.close()


def test_exists_and_delete(tmp_storage):
    """exists / delete"""
    path = tmp_storage.save_resume("c1", "pdf", b"x")
    assert tmp_storage.exists(path)
    assert tmp_storage.delete(path) is True
    assert not tmp_storage.exists(path)
    # 二次删除返回 False
    assert tmp_storage.delete(path) is False


# ===== LLM 测试（mocked OpenAI）=====

def test_chat_returns_text():
    """chat() 返回文本"""
    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "Hello, world!"

    with patch("app.services.llm_service.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_get_client.return_value = mock_client

        result = chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"
        mock_client.chat.completions.create.assert_called_once()


def test_chat_json_returns_pydantic_instance():
    """chat_json() 返回校验过的 Pydantic 实例"""

    class TestSchema(BaseModel):
        name: str
        age: int

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = json.dumps({"name": "Alice", "age": 30})

    with patch("app.services.llm_service.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_get_client.return_value = mock_client

        result = chat_json(
            [{"role": "user", "content": "test"}],
            schema=TestSchema,
        )
        assert isinstance(result, TestSchema)
        assert result.name == "Alice"
        assert result.age == 30


def test_chat_json_validates_schema():
    """chat_json() 会用 Pydantic 校验，失败抛 ValidationError"""
    class TestSchema(BaseModel):
        name: str
        age: int

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = json.dumps({"name": "Alice"})  # 缺 age

    with patch("app.services.llm_service.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_get_client.return_value = mock_client

        with pytest.raises(Exception):  # ValidationError
            chat_json([{"role": "user"}], schema=TestSchema)


def test_chat_json_extracts_code_block():
    """LLM 输出在 ```json ... ``` 里时能正确解析"""
    class TestSchema(BaseModel):
        result: str

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    # LLM 在 markdown code block 里输出
    fake_response.choices[0].message.content = (
        '```json\n{"result": "ok"}\n```'
    )

    with patch("app.services.llm_service.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_get_client.return_value = mock_client

        result = chat_json([{"role": "user"}], schema=TestSchema)
        assert result.result == "ok"


def test_chat_retries_on_rate_limit():
    """429 RateLimitError 触发重试"""
    from openai import RateLimitError

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "ok"

    with patch("app.services.llm_service.get_client") as mock_get_client, \
         patch("app.services.llm_service.time.sleep") as mock_sleep:  # 跳过 sleep
        mock_client = MagicMock()
        # 第一次 RateLimitError，第二次成功
        rate_err = RateLimitError("rate limited", response=MagicMock(), body={})
        mock_client.chat.completions.create.side_effect = [rate_err, fake_response]
        mock_get_client.return_value = mock_client

        result = chat([{"role": "user", "content": "x"}], max_retries=2)
        assert result == "ok"
        assert mock_client.chat.completions.create.call_count == 2
        # 验证指数退避：第一次失败后 wait 2^0 = 1s
        mock_sleep.assert_called_once_with(1)


def test_chat_does_not_retry_on_4xx():
    """4xx 错误（除 429）不重试"""
    from openai import APIError

    with patch("app.services.llm_service.get_client") as mock_get_client, \
         patch("app.services.llm_service.time.sleep") as mock_sleep:
        mock_client = MagicMock()
        # 4xx 错误
        err = APIError("bad request", request=MagicMock(), body={})
        # APIError 没有 status_code 字段，要用 MagicMock 模拟
        err.status_code = 400
        mock_client.chat.completions.create.side_effect = err
        mock_get_client.return_value = mock_client

        with pytest.raises(APIError):
            chat([{"role": "user"}], max_retries=3)
        # 只调用 1 次（不重试）
        assert mock_client.chat.completions.create.call_count == 1
        # 没 sleep
        mock_sleep.assert_not_called()


def test_extract_json_block_handles_various_formats():
    """测试 JSON 块提取工具函数"""
    # 1. 普通 JSON
    assert _extract_json_block('{"a": 1}') == '{"a": 1}'
    # 2. markdown json block
    assert _extract_json_block('```json\n{"a": 1}\n```') == '{"a": 1}'
    # 3. markdown block (no json tag)
    assert _extract_json_block('```\n{"a": 1}\n```') == '{"a": 1}'
    # 4. 无格式
    assert _extract_json_block('  {"a": 1}  ').strip() == '{"a": 1}'


# ===== Whisper 测试（条件 skip）=====

def test_whisper_load_and_unload():
    """测试 Whisper 模型加载（不实际跑模型，避免下载 ~150MB）"""
    from app.services import asr_service

    # 初始状态
    assert asr_service.is_loaded() is False
    assert asr_service.get_model() is None

    # 模拟设置一个假模型（不真加载）
    asr_service._whisper_model = MagicMock()
    asr_service._whisper_device = "cpu"
    assert asr_service.is_loaded() is True

    # 释放
    asr_service.release_whisper_model()
    assert asr_service.is_loaded() is False
    assert asr_service.get_model() is None


def test_whisper_detect_device_returns_string():
    """设备检测返回 cuda 或 cpu"""
    from app.services import asr_service

    device = asr_service.detect_device()
    assert device in ("cuda", "cpu")


def test_whisper_transcribe_requires_loaded_model():
    """未加载模型时 transcribe 抛错"""
    from app.services import asr_service

    # 强制模型未加载
    asr_service._whisper_model = None
    asr_service._whisper_device = None

    # Patch 懒加载，让它保持 None（不实际下载模型）
    with patch("app.services.asr_service.load_whisper_model") as mock_load:
        # 确保懒加载不会成功
        mock_load.return_value = None

        with pytest.raises(RuntimeError, match="未加载"):
            asr_service.transcribe("/fake/path.wav")


@pytest.mark.skip(reason="需要真实音频文件和 Whisper 模型，跳过")
def test_whisper_transcribe_real_audio():
    """真实转写测试（需准备 webm/wav 文件，CI 跳过）"""
    from app.services import asr_service

    if not asr_service.is_loaded():
        asr_service.load_whisper_model()
    text = asr_service.transcribe("tests/fixtures/test_audio_zh.wav", language="zh")
    assert len(text) > 0