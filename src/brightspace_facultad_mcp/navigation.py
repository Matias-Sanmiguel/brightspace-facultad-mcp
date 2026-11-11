"""Bounded UI reads and origin checks for the observed UADE Brightspace UI."""
from __future__ import annotations

import asyncio
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .core import AppError

ORIGIN = 'https://virtualbsp.uade.edu.ar'
HOME = ORIGIN + '/d2l/home'


def local_url(value: str, base: str = HOME) -> str:
    value = urljoin(base, value)
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.hostname != 'virtualbsp.uade.edu.ar'
            or parts.port not in (None, 443) or parts.username or parts.password):
        raise AppError('origen_no_permitido', 'El recurso está fuera de Brightspace UADE; abrilo manualmente.')
    return value


def public_source(value: str) -> str:
    parts = urlsplit(local_url(value))
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query)
                       if k in {'ou', 'db', 'grpid'} and v.isdigit()])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))


async def links(scope) -> list[dict]:
    # Locator selection pierces open shadow roots; document.querySelectorAll does not.
    return await scope.locator('a[href]').evaluate_all('''nodes => nodes.filter(a => a.getClientRects().length).map(a => ({
        href:a.href, text:(a.innerText || a.getAttribute('aria-label') || a.title || '').trim(),
        label:a.getAttribute('aria-label') || '', title:a.title || '',
        context:(a.closest('li') || a.parentElement || a).innerText.slice(0, 2000)
    }))''')


async def bounded_text(scope, maximum: int = 2_000_000) -> tuple[str, bool]:
    # Brightspace's rich text lives in open shadow roots, absent from innerText.
    # Walk the composed tree in order, including slots, with a strict output cap.
    return await scope.evaluate('''(el, maximum) => {
        const parts=[]; let size=0, truncated=false;
        function add(text) {
            const remaining=maximum-size;
            if (text.length>remaining) { truncated=true; text=text.slice(0,remaining); }
            parts.push(text); size+=text.length;
        }
        function walk(node) {
            if(size>=maximum) {truncated=true;return;}
            if(node.nodeType===Node.TEXT_NODE) {
                if(node.textContent.trim()) add(node.textContent.replace(/\\s+/g,' '));
                return;
            }
            if(node.nodeType!==Node.ELEMENT_NODE) return;
            if(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(node.tagName)) return;
            const style=getComputedStyle(node);
            if(style.display==='none'||style.visibility==='hidden'||node.hidden) return;
            const block=!['inline','contents','inline-block'].includes(style.display);
            if(block||node.tagName==='BR') add('\\n');
            const assigned=node.tagName==='SLOT' ? node.assignedNodes({flatten:true}) : [];
            const children=assigned.length ? assigned : (node.shadowRoot||node).childNodes;
            for(const child of children) {walk(child);if(size>=maximum) break;}
            if(block) add('\\n');
        }
        walk(el);
        const text=parts.join('').replace(/[ \\t]+/g,' ').replace(/ *\\n */g,'\\n').replace(/\\n{3,}/g,'\\n\\n').trim();
        return [text.slice(0,maximum),!truncated];
    }''', maximum)


async def settled(page, timeout_ms: int) -> bool:
    """A loading widget must never become a successful empty collection."""
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    while True:
        loading = page.get_by_text(re.compile(r'^(Cargando(?:\.{3}|…)?|Loading(?:\.{3}|…)?)$', re.I))
        visible = any([await item.is_visible() for item in await loading.all()])
        if not visible:
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(.1)


async def has_more(page) -> bool:
    for role in ['button', 'link']:
        candidate = page.get_by_role(role, name=re.compile(r'^(Siguiente(?: página)?|Next(?: page)?|Cargar más|Load more)$', re.I))
        for item in await candidate.all():
            if await item.is_visible() and await item.is_enabled():
                return True
    return False


def document_kind(description: str) -> str:
    text = description.lower()
    for words, kind in [
        (('cuestionario', 'quiz', 'examen'), 'cuestionario'),
        (('asignación', 'assignment', 'dropbox'), 'asignacion'),
        (('pdf',), 'pdf'), (('powerpoint', 'pptx'), 'pptx'),
        (('word', 'docx'), 'docx'), (('página web', 'web page', 'html'), 'html'),
        (('video', 'audio', 'multimedia'), 'multimedia'),
    ]:
        if any(word in text for word in words):
            return kind
    return 'otro'
