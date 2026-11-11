"""Bounded document text extraction. No macros, network requests or OCR."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import asyncio
import json
import sys
import anyio

from docx import Document
from pptx import Presentation
from pypdf import PdfReader

from .core import AppError

MAX_TEXT = 2_000_000


def text_page(text: str, offset: int = 0, limit: int = 10000) -> dict:
    if not 1 <= limit <= 10000 or offset < 0 or offset > len(text):
        raise AppError('pagina_invalida', 'El offset debe estar dentro del texto y el límite entre 1 y 10000.')
    end = min(offset + limit, len(text))
    return {'texto': text[offset:end], 'siguiente_offset': end if end < len(text) else None,
            'completo': end == len(text), 'total_caracteres': len(text)}


def extract_document(path: Path, max_bytes: int = 25 * 1024 * 1024,
                     max_expanded_bytes: int = 100 * 1024 * 1024) -> dict:
    if path.stat().st_size > max_bytes:
        raise AppError('archivo_grande', 'El archivo supera el máximo permitido de 25 MiB.')
    suffix = path.suffix.lower()
    if suffix not in {'.pdf', '.docx', '.pptx'}:
        raise AppError('formato_no_soportado', 'Se admiten DOCX, PPTX y PDF con texto; no OCR, video o audio.')
    try:
        if suffix in {'.docx', '.pptx'}:
            with ZipFile(path) as archive:
                if len(archive.infolist()) > 10000 or sum(i.file_size for i in archive.infolist()) > max_expanded_bytes:
                    raise AppError('contenido_grande', 'El documento descomprimido supera el límite de procesamiento.')
        parts = []
        size = 0
        truncated = False

        def append(text: str) -> bool:
            nonlocal size, truncated
            remaining = MAX_TEXT - size
            if len(text) > remaining:
                parts.append(text[:remaining])
                truncated = True
                size = MAX_TEXT
                return False
            parts.append(text)
            size += len(text) + 2
            if size >= MAX_TEXT:
                truncated = True
            return size < MAX_TEXT

        if suffix == '.docx':
            document = Document(path)
            for block in document.iter_inner_content():
                text = block.text if hasattr(block, 'text') else '\n'.join(' | '.join(c.text for c in r.cells) for r in block.rows)
                if not append(text):
                    break
        elif suffix == '.pptx':
            presentation = Presentation(path)
            for number, slide in enumerate(presentation.slides, 1):
                text = [f'Diapositiva {number}']
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        text.append(shape.text)
                    elif shape.has_table:
                        text.extend(' | '.join(c.text for c in row.cells) for row in shape.table.rows)
                if not append('\n'.join(text)):
                    break
        else:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise AppError('documento_cifrado', 'El PDF requiere contraseña; no se procesa automáticamente.')
            decoded_bytes = 0
            if len(reader.pages) > 1000:
                raise AppError('contenido_grande', 'El PDF supera el máximo de 1000 páginas.')
            for number, page in enumerate(reader.pages, 1):
                content = page.get_contents()
                if content is not None:
                    decoded_bytes += len(content.get_data())
                if decoded_bytes > max_expanded_bytes:
                    raise AppError('contenido_grande', 'El contenido total del PDF supera el límite de procesamiento.')
                if not append(page.extract_text() or ''):
                    break
        text = '\n\n'.join(parts).strip()
        if not text:
            raise AppError('sin_texto', 'No se encontró texto extraíble. Puede ser un archivo vacío, escaneado o formado por imágenes; no se incluye OCR.')
        return {'texto': text, 'extraccion_completa': not truncated,
                'aviso': 'Texto extraído; imágenes, notas, diagramas y formato pueden no estar representados.' + (' Se alcanzó el límite de 2 millones de caracteres.' if truncated else '')}
    except AppError:
        raise
    except Exception as exc:
        raise AppError('documento_invalido', 'No se pudo leer el documento; verificá su formato o abrilo manualmente.') from exc


async def extract_async(path: Path, max_bytes: int = 25 * 1024 * 1024, timeout: float = 30) -> dict:
    """Run parsers in a killable worker, so cancellation cannot strand a parser."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,'-m','brightspace_facultad_mcp.document_worker',str(path),str(max_bytes),
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        try:
            output,_=await asyncio.wait_for(process.communicate(),timeout=timeout)
        except TimeoutError as exc:
            raise AppError('procesamiento_agotado','El documento superó el tiempo de procesamiento permitido.') from exc
        if process.returncode:
            raise AppError('procesamiento_agotado','El proceso de lectura excedió sus recursos o se cerró inesperadamente.')
        result=json.loads(output)
        if not result['ok']:
            raise AppError(result['error'],result['mensaje'])
        return result['documento']
    finally:
        with anyio.CancelScope(shield=True):
            if process.returncode is None:
                process.kill()
            await process.wait()
