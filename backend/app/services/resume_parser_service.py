"""
简历解析服务（§11）

支持 PDF（PyPDF2）和 DOCX（python-docx）：
- parse_resume(file_path, file_type)：同步阻塞（被 background thread 用 executor 调）
- parse_resume_async(file_path, file_type)：async 版本，run_in_executor
- 损坏文件 / 加密 PDF / 扫描件 全部 catch 异常 + 返回错误信息
"""
import io
import logging
from pathlib import Path
from typing import Literal


logger = logging.getLogger(__name__)


# ===== 错误类型 =====

class ResumeParseError(Exception):
    """简历解析失败的基类"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ===== 主函数 =====

def parse_resume(
    file_path: str | Path,
    file_type: Literal["pdf", "docx"],
    timeout_seconds: int = 30,
) -> str:
    """
    同步解析简历文件

    Args:
        file_path: 文件路径（PDF 或 DOCX）
        file_type: "pdf" 或 "docx"
        timeout_seconds: 超时（秒）

    Returns:
        解析后的纯文本

    Raises:
        ResumeParseError: 解析失败（带 error_code）
    """
    path = Path(file_path)
    if not path.exists():
        raise ResumeParseError("FILE_NOT_FOUND", f"文件不存在: {path}")

    if file_type == "pdf":
        return _parse_pdf(path)
    elif file_type == "docx":
        return _parse_docx(path)
    else:
        raise ResumeParseError("UNSUPPORTED_TYPE", f"不支持的文件类型: {file_type}")


def _parse_pdf(path: Path) -> str:
    """解析 PDF（PyPDF2）"""
    try:
        import PyPDF2
    except ImportError:
        raise ResumeParseError("DEPENDENCY_MISSING", "PyPDF2 未安装")

    try:
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)

            # 检查加密
            if reader.is_encrypted:
                raise ResumeParseError("ENCRYPTED_PDF", "PDF 已加密")

            # 提取每页文本
            for page in reader.pages:
                try:
                    text = page.extract_text() or ""
                    text_parts.append(text)
                except Exception as e:
                    logger.warning(f"pdf_page_extract_failed page={len(text_parts)} exc={e}")
                    continue

        full_text = "\n".join(text_parts).strip()

        if not full_text:
            raise ResumeParseError("SCANNED_PDF", "PDF 可能为扫描件，无可提取文本")

        return full_text

    except ResumeParseError:
        raise
    except Exception as e:
        raise ResumeParseError("PARSE_FAILED", f"PDF 解析失败: {e}")


def _parse_docx(path: Path) -> str:
    """解析 DOCX（python-docx）"""
    try:
        from docx import Document
    except ImportError:
        raise ResumeParseError("DEPENDENCY_MISSING", "python-docx 未安装")

    try:
        doc = Document(str(path))
        text_parts = [p.text for p in doc.paragraphs if p.text.strip()]

        # 也读表格（很多简历用表格）
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)

        full_text = "\n".join(text_parts).strip()

        if not full_text:
            raise ResumeParseError("EMPTY_DOCX", "DOCX 文件无可提取文本")

        return full_text

    except ResumeParseError:
        raise
    except Exception as e:
        raise ResumeParseError("PARSE_FAILED", f"DOCX 解析失败: {e}")


async def parse_resume_async(
    file_path: str | Path,
    file_type: Literal["pdf", "docx"],
) -> str:
    """
    异步版本（实际跑在线程池里）

    用法（在 async context）：
        text = await resume_parser_service.parse_resume_async(file_path, "pdf")
    """
    from functools import partial
    from app.core.main_loop import get_main_loop
    import asyncio

    loop = get_main_loop()
    return await loop.run_in_executor(
        None,
        partial(parse_resume, file_path, file_type),
    )


# ===== 便捷函数：从 bytes 解析 =====

def parse_pdf_bytes(content: bytes) -> str:
    """从 PDF bytes 直接解析（不写文件）"""
    try:
        import PyPDF2
    except ImportError:
        raise ResumeParseError("DEPENDENCY_MISSING", "PyPDF2 未安装")

    try:
        text_parts = []
        reader = PyPDF2.PdfReader(io.BytesIO(content))

        if reader.is_encrypted:
            raise ResumeParseError("ENCRYPTED_PDF", "PDF 已加密")

        for page in reader.pages:
            try:
                text = page.extract_text() or ""
                text_parts.append(text)
            except Exception as e:
                logger.warning(f"pdf_page_extract_failed exc={e}")
                continue

        full_text = "\n".join(text_parts).strip()
        if not full_text:
            raise ResumeParseError("SCANNED_PDF", "PDF 可能为扫描件")

        return full_text

    except ResumeParseError:
        raise
    except Exception as e:
        raise ResumeParseError("PARSE_FAILED", f"PDF bytes 解析失败: {e}")


def parse_docx_bytes(content: bytes) -> str:
    """从 DOCX bytes 直接解析（不写文件）"""
    try:
        from docx import Document
    except ImportError:
        raise ResumeParseError("DEPENDENCY_MISSING", "python-docx 未安装")

    try:
        doc = Document(io.BytesIO(content))
        text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)

        full_text = "\n".join(text_parts).strip()
        if not full_text:
            raise ResumeParseError("EMPTY_DOCX", "DOCX 无可提取文本")
        return full_text

    except ResumeParseError:
        raise
    except Exception as e:
        raise ResumeParseError("PARSE_FAILED", f"DOCX bytes 解析失败: {e}")