from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from docx import Document
from pptx import Presentation
from pypdf import PdfWriter
from brightspace_facultad_mcp.core import AppError
from brightspace_facultad_mcp.documents import extract_document, text_page


def test_docx_paragraphs_and_tables(tmp_path):
    file = tmp_path / 'test.docx'
    doc = Document()
    doc.add_paragraph('Consigna de ejemplo')
    doc.add_table(rows=1, cols=2).rows[0].cells[1].text = 'Fecha límite'
    doc.save(file)
    result = extract_document(file)
    assert 'Consigna de ejemplo' in result['texto']
    assert 'Fecha límite' in result['texto']


def test_pptx_text(tmp_path):
    file = tmp_path / 'test.pptx'
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = 'Patrones de diseño'
    presentation.save(file)
    assert 'Patrones de diseño' in extract_document(file)['texto']


def test_pdf_without_text_reported(tmp_path):
    file = tmp_path / 'blank.pdf'
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.write(file)
    with pytest.raises(AppError, match='sin_texto'):
        extract_document(file)


def test_document_size_and_format_bounds(tmp_path):
    file = tmp_path / 'huge.docx'
    file.write_bytes(b'x' * 100)
    with pytest.raises(AppError, match='archivo_grande'):
        extract_document(file, max_bytes=50)
    file = tmp_path / 'unsupported.exe'
    file.write_bytes(b'x')
    with pytest.raises(AppError, match='formato_no_soportado'):
        extract_document(file)


def test_expanded_zip_size_bounded(tmp_path):
    file = tmp_path / 'bomb.docx'
    with ZipFile(file, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', b'A' * 3000)
    with pytest.raises(AppError, match='contenido_grande'):
        extract_document(file, max_expanded_bytes=1000)


def test_corrupt_document_has_actionable_error(tmp_path):
    file = tmp_path / 'broken.docx'
    file.write_bytes(b'broken')
    with pytest.raises(AppError, match='documento_invalido'):
        extract_document(file)


def test_text_pages_never_silently_truncate():
    first = text_page('A' * 23000, offset=0, limit=10000)
    assert len(first['texto']) == 10000
    assert first['siguiente_offset'] == 10000
    assert first['completo'] is False
    last = text_page('A' * 23000, offset=20000, limit=10000)
    assert len(last['texto']) == 3000 and last['siguiente_offset'] is None
    with pytest.raises(AppError):
        text_page('x', offset=-1)
