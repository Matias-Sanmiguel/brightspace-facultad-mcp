"""Temporary browser downloads with transfer and parser budgets."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
import re
import secrets

import anyio
from playwright.async_api import Error as BrowserError

from .core import AppError
from .documents import extract_async
from .navigation import bounded_text, local_url


async def read_download(browser, ref: dict) -> dict:
    page = browser.page
    button = page.get_by_role('button', name=re.compile(r'^(Descargar|Download)$', re.I)).first
    if ref.get('parent_url'):
        button=None
        for candidate in await page.locator('a[href]').all():
            href=await candidate.get_attribute('href')
            try:
                if local_url(href,page.url)==ref['url']:
                    button=candidate
                    break
            except AppError:
                continue
        if button is None:
            raise AppError('referencia_desactualizada','El adjunto ya no aparece en la consigna; volvé a leerla.')
    if not await button.count():
        for frame in page.frames:
            if frame.url.startswith('https://virtualbsp.uade.edu.ar/d2l/common/assets/pdfjs'):
                local_url(frame.url)
                text, _ = await bounded_text(frame.locator('#viewer'))
                if text.strip():
                    return {'texto':text, 'extraccion_completa':False,
                            'aviso':'Texto parcial del visor; solo incluye páginas cargadas. No se pudo descargar el original.'}
        raise AppError('descarga_no_disponible', 'No se encontró Descargar ni un visor con texto accesible.')
    directory = browser.download_dir
    if directory is None:
        raise AppError('descarga_no_disponible', 'El navegador no tiene un directorio temporal de descarga.')
    baseline = set(directory.rglob('*'))
    path = directory / (secrets.token_hex(16)+'.'+ref['tipo'])
    async def acquire():
        async with page.expect_download(timeout=browser.settings.timeout_ms) as pending:
            await button.click()
        return await pending.value
    acquisition = asyncio.create_task(acquire())
    download = transfer = None
    deadline = asyncio.get_running_loop().time() + browser.settings.timeout_ms/1000
    try:
        download = await asyncio.shield(acquisition)
        local_url(download.url)
        transfer = asyncio.create_task(download.save_as(path))
        while not transfer.done():
            sizes=[]
            for artifact in directory.rglob('*'):
                if artifact not in baseline:
                    with suppress(OSError):
                        if artifact.is_file():
                            sizes.append(artifact.stat().st_size)
            if max(sizes, default=0)>browser.settings.max_file_bytes:
                raise AppError('archivo_grande', 'El archivo supera el límite de 25 MiB.')
            if asyncio.get_running_loop().time()>=deadline:
                raise AppError('descarga_agotada', 'La descarga superó el tiempo permitido.')
            await asyncio.wait({transfer}, timeout=.05)
        await transfer
        if path.stat().st_size>browser.settings.max_file_bytes:
            raise AppError('archivo_grande', 'El archivo supera el límite de 25 MiB.')
        return await extract_async(path, max_bytes=browser.settings.max_file_bytes)
    finally:
        with anyio.CancelScope(shield=True):
            if download is None:
                with suppress(BrowserError, asyncio.CancelledError):
                    download = await acquisition
            if download:
                with suppress(BrowserError):
                    await download.cancel()
            if transfer:
                if not transfer.done():
                    transfer.cancel()
                await asyncio.gather(transfer, return_exceptions=True)
            if download:
                with suppress(BrowserError):
                    await download.delete()
            path.unlink(missing_ok=True)
            for artifact in directory.rglob('*'):
                if artifact not in baseline and artifact.is_file():
                    with suppress(OSError):
                        artifact.unlink(missing_ok=True)
