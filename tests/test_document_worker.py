import pytest
from docx import Document
from brightspace_facultad_mcp.documents import extract_async
from brightspace_facultad_mcp.core import AppError


async def test_document_worker_extracts_without_browser(tmp_path):
    file=tmp_path/'test.docx'
    doc=Document();doc.add_paragraph('Contenido del documento');doc.save(file)
    assert 'Contenido del documento' in (await extract_async(file))['texto']


async def test_document_worker_timeout_is_bounded(tmp_path):
    file=tmp_path/'test.docx'
    doc=Document();doc.add_paragraph('Contenido');doc.save(file)
    with pytest.raises(AppError,match='procesamiento_agotado'):
        await extract_async(file,timeout=.001)


@pytest.mark.parametrize('worker_encoding', ['cp1252', 'ascii'])
async def test_document_worker_preserves_unicode_with_non_utf8_stdout(tmp_path, monkeypatch, worker_encoding):
    # The child inherits Windows-style stdout settings; the wire format must
    # still preserve arbitrary document text as JSON, independently of locale.
    monkeypatch.setenv('PYTHONIOENCODING', worker_encoding)
    file = tmp_path / 'guía.docx'
    text = 'Programación: análisis, ñ, 中文, 📚'
    doc = Document()
    doc.add_paragraph(text)
    doc.save(file)
    result = await extract_async(file)
    assert text in result['texto']
    assert result['extraccion_completa'] is True
