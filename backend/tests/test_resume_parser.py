"""
简历解析服务测试
"""
import io
from pathlib import Path

import pytest

from app.services.resume_parser_service import (
    parse_pdf_bytes,
    parse_docx_bytes,
    parse_resume,
    ResumeParseError,
)


# ===== PDF 测试 =====

def test_parse_pdf_bytes_simple_text():
    """解析含简单文本的 PDF"""
    # 构造一个最小 PDF（用 PyPDF2 测试 PDF）
    import PyPDF2
    from PyPDF2 import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # PyPDF2 不直接支持写入文本，这里只测空 PDF（不会报错）

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    pdf_bytes = buf.read()

    # 空 PDF 应该触发 SCANNED_PDF 错误（无文本可提取）
    with pytest.raises(ResumeParseError) as exc:
        parse_pdf_bytes(pdf_bytes)
    assert exc.value.code in ("SCANNED_PDF", "PARSE_FAILED")


def test_parse_pdf_bytes_invalid():
    """解析无效的 PDF 数据"""
    invalid_pdf = b"this is not a valid pdf"
    with pytest.raises(ResumeParseError):
        parse_pdf_bytes(invalid_pdf)


def test_parse_pdf_bytes_empty():
    """解析空 bytes"""
    with pytest.raises(ResumeParseError):
        parse_pdf_bytes(b"")


def test_parse_docx_bytes_invalid():
    """解析无效的 DOCX 数据"""
    invalid_docx = b"this is not a valid docx"
    with pytest.raises(ResumeParseError):
        parse_docx_bytes(invalid_docx)


def test_parse_docx_bytes_empty():
    """解析空 bytes"""
    with pytest.raises(ResumeParseError):
        parse_docx_bytes(b"")


def test_parse_resume_unsupported_type(tmp_path: Path):
    """不支持的文件类型（文件存在但 type 参数不支持）"""
    fake = tmp_path / "resume.unsupported"
    fake.write_bytes(b"x")
    with pytest.raises(ResumeParseError) as exc:
        parse_resume(str(fake), "exe")  # type 参数无效
    assert exc.value.code == "UNSUPPORTED_TYPE"


def test_parse_resume_file_not_found():
    """文件不存在"""
    with pytest.raises(ResumeParseError) as exc:
        parse_resume("Z:/nonexistent_xyz_12345/path.pdf", "pdf")
    assert exc.value.code == "FILE_NOT_FOUND"


# ===== 真实 DOCX 测试 =====

def test_parse_real_docx():
    """解析真实 DOCX 文件"""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx 未安装")

    buf = io.BytesIO()
    doc = Document()
    doc.add_heading("John Doe Resume", 0)
    doc.add_paragraph("Email: john@example.com")
    doc.add_paragraph("Experience: 5 years Python development")
    doc.add_paragraph("Skills: Python, FastAPI, LangChain")
    doc.save(buf)
    buf.seek(0)
    docx_bytes = buf.read()

    text = parse_docx_bytes(docx_bytes)
    assert "John Doe" in text
    assert "john@example.com" in text
    assert "Python" in text
    assert "FastAPI" in text
    assert "LangChain" in text


def test_parse_real_docx_with_table():
    """解析带表格的 DOCX"""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx 未安装")

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Skills Matrix:")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Python"
    table.cell(0, 1).text = "Advanced"
    table.cell(1, 0).text = "Java"
    table.cell(1, 1).text = "Intermediate"
    doc.save(buf)
    buf.seek(0)
    docx_bytes = buf.read()

    text = parse_docx_bytes(docx_bytes)
    assert "Skills Matrix" in text
    assert "Python" in text
    assert "Java" in text
    assert "Advanced" in text
    assert "Intermediate" in text


def test_parse_resume_via_path(tmp_path: Path):
    """通过文件路径解析"""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx 未安装")

    # 创建临时 docx 文件
    doc = Document()
    doc.add_paragraph("Test Resume Content")
    docx_path = tmp_path / "resume.docx"
    doc.save(str(docx_path))

    text = parse_resume(docx_path, "docx")
    assert "Test Resume Content" in text


def test_parse_resume_via_path_wrong_extension():
    """通过路径解析但扩展名错误"""
    with pytest.raises(ResumeParseError):
        parse_resume("/tmp/fake.txt", "pdf")  # 扩展名是 .txt 但声明 pdf