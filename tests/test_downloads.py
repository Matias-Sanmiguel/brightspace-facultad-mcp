import asyncio
import io
from dataclasses import replace
import pytest
from pptx import Presentation
from brightspace_facultad_mcp.core import AppError
from test_brightspace import service, course

async def prepare(service, tmp_path):
    materia = await course(service)
    listing = await service.call('listar_archivos', materia_id=materia)
    doc = next(item for item in listing['items'] if item['tipo']=='pptx')
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[1]).shapes.title.text = 'Arquitectura del sistema'
    stream = io.BytesIO(); deck.save(stream)
    await service.browser.page.route('**/slides.pptx', lambda r:r.fulfill(body=stream.getvalue(), headers={
        'content-type':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'content-disposition':'attachment; filename="slides.pptx"'}))
    service.browser.download_dir=tmp_path
    return doc['id']

async def test_browser_download_extracts_presentation_and_cleans_temp(service, tmp_path):
    doc=await prepare(service, tmp_path)
    result=await service.call('leer_documento', archivo_id=doc)
    assert 'Arquitectura del sistema' in result['texto']
    assert not list(tmp_path.glob('*.pptx'))

async def test_oversized_download_returns_error_and_cleans_temp(service, tmp_path):
    doc=await prepare(service, tmp_path)
    service.browser.settings=replace(service.browser.settings, max_file_bytes=100)
    with pytest.raises(AppError, match='archivo_grande'):
        await service.call('leer_documento', archivo_id=doc)
    assert not list(tmp_path.glob('*.pptx'))

async def test_cancellation_at_download_event_cleans_transfer(service, tmp_path):
    doc=await prepare(service, tmp_path)
    service.browser.page.once('download', lambda download:task.cancel())
    task=asyncio.create_task(service.call('leer_documento', archivo_id=doc))
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not list(tmp_path.glob('*.pptx'))
