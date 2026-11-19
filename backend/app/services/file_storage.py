"""
文件存储服务（§11 + §16.3 借鉴 GraphRAGAgent）

LocalFileStorage 实现：
- 原子写入（temp + rename，防止崩溃留半截文件）
- 简历 / 音频 / 报告三类文件
- 接口抽象（FileStorage Protocol，Phase 5 可换 S3）

借鉴 GraphRAGAgent 的 atomic write 模式：
    1. write to .tmp
    2. os.replace(tmp, target)  ← 原子操作
"""
import logging
import os
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import settings


logger = logging.getLogger(__name__)


# ===== Protocol（Phase 5 可换 S3）=====
class FileStorage(Protocol):
    """文件存储抽象接口"""

    def save_resume(self, candidate_id: str, file_ext: str, content: bytes) -> Path:
        """保存候选人简历，返回路径"""
        ...

    def save_audio(self, interview_id: int, question_id: int, content: bytes) -> Path:
        """保存候选人答题音频"""
        ...

    def save_report(self, interview_id: int, content: bytes) -> Path:
        """保存面试报告 PDF"""
        ...

    def read(self, path: Path) -> bytes:
        ...

    def stream(self, path: Path) -> BinaryIO:
        ...


# ===== LocalFileStorage 实现 =====
class LocalFileStorage:
    """本地文件系统存储实现"""

    def __init__(self, root_dir: str | Path | None = None):
        self.root = Path(root_dir or settings.STORAGE_PATH).resolve()

    # ===== 路径生成 =====

    def _resume_path(self, candidate_id: str, file_ext: str) -> Path:
        """简历路径：storage/resumes/{candidate_id}/original.{ext}"""
        return self.root / "resumes" / candidate_id / f"original.{file_ext}"

    def _audio_path(self, interview_id: int, question_id: int, file_ext: str = "webm") -> Path:
        """答题音频路径：storage/audio/{interview_id}/{question_id}.{ext}"""
        return self.root / "audio" / str(interview_id) / f"{question_id}.{file_ext}"

    def _report_path(self, interview_id: int) -> Path:
        """报告路径：storage/reports/{interview_id}.pdf"""
        return self.root / "reports" / f"{interview_id}.pdf"

    # ===== 原子写入（§16.3 借鉴） =====

    def _save_atomic(self, target_path: Path, content: bytes) -> Path:
        """
        原子写入：先写 .tmp，再 os.replace

        为什么原子：rename 是 POSIX 原子操作，崩溃/断电不会留半截文件
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 临时文件（同目录，确保 rename 是原子操作）
        tmp = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            with open(tmp, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # 强制刷盘
            os.replace(tmp, target_path)  # 原子 rename
            logger.debug("file_saved_atomic", extra={"path": str(target_path)})
            return target_path
        except Exception:
            # 清理临时文件
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            raise

    # ===== 公开方法 =====

    def save_resume(self, candidate_id: str, file_ext: str, content: bytes) -> Path:
        """保存候选人简历（PDF/DOCX）"""
        # 清理扩展名（去除 . 只留 pdf/docx）
        file_ext = file_ext.lstrip(".").lower()
        if file_ext not in ("pdf", "docx"):
            raise ValueError(f"Unsupported resume file extension: {file_ext}")

        path = self._resume_path(candidate_id, file_ext)
        return self._save_atomic(path, content)

    def save_audio(self, interview_id: int, question_id: int, content: bytes) -> Path:
        """保存候选人答题音频（webm）"""
        path = self._audio_path(interview_id, question_id, "webm")
        return self._save_atomic(path, content)

    def save_report(self, interview_id: int, content: bytes) -> Path:
        """保存面试报告 PDF"""
        path = self._report_path(interview_id)
        return self._save_atomic(path, content)

    def read(self, path: Path) -> bytes:
        """读取文件全部内容"""
        return Path(path).read_bytes()

    def stream(self, path: Path) -> BinaryIO:
        """以二进制流方式打开文件（用于 PDF 下载等）"""
        return open(Path(path), "rb")

    def exists(self, path: Path) -> bool:
        return Path(path).exists()

    def delete(self, path: Path) -> bool:
        """删除文件（不存在则返回 False）"""
        try:
            Path(path).unlink()
            return True
        except FileNotFoundError:
            return False


# ===== 全局单例 =====
_storage: LocalFileStorage | None = None


def get_file_storage() -> LocalFileStorage:
    """获取全局文件存储实例"""
    global _storage
    if _storage is None:
        _storage = LocalFileStorage()
    return _storage