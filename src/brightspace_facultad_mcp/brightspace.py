"""Read academic resources through the same Brightspace UI the student uses."""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit
from playwright.async_api import TimeoutError as BrowserTimeout

from .browser import BrowserSession
from .core import AppError, Paginator, ReferenceStore, Settings
from .documents import MAX_TEXT, text_page
from .navigation import HOME, bounded_text, document_kind, has_more, links, local_url, public_source, settled


class BrightspaceService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.browser = BrowserSession(settings)
        self.refs = ReferenceStore()
        self.pages = Paginator()
        self.texts = ReferenceStore(capacity=8)

    async def close(self):
        await self.browser.close()

    async def call(self, name: str, **kwargs) -> dict:
        methods = {'estado_conexion': self.browser.status, 'iniciar_sesion': self.browser.login,
                   'listar_materias': self.listar_materias, 'listar_tareas': self.listar_tareas,
                   'leer_tarea': self.leer_tarea, 'leer_anuncios': self.leer_anuncios,
                   'listar_archivos': self.listar_archivos, 'leer_documento': self.leer_documento}
        if name not in methods:
            raise AppError('herramienta_invalida', 'La herramienta no existe.')
        async with self.browser.lock:
            return await methods[name](**kwargs)

    async def go(self, url: str):
        url = local_url(url)
        page = await self.browser.require_page()
        await page.goto(url, wait_until='domcontentloaded')
        local_url(page.url)
        if await self.browser.page_state(page) == 'autenticacion_pendiente':
            raise AppError('autenticacion_pendiente', 'Volvé a ingresar con el comando login del navegador dedicado.')
        denied = page.get_by_text(re.compile(r'^(No autorizado|Acceso denegado|Not authorized|Access denied)$', re.I))
        if await denied.count() and await denied.first.is_visible():
            raise AppError('acceso_denegado', 'Tu cuenta no puede abrir este recurso.')
        return page

    async def course_page(self, materia_id: str, section: str):
        ref = self.refs.get(materia_id, 'materia')
        page = await self.go(ref['url'])
        candidates = await links(page)
        pattern = {'tareas': r'/d2l/lms/dropbox/(?:dropbox|user/folders_list)\.d2l',
                   'archivos': r'/d2l/le/content/\d+/Home',
                   'anuncios': r'/d2l/lms/news/main\.d2l'}[section]
        for link in candidates:
            if re.search(pattern, link['href']):
                return await self.go(link['href'])
        raise AppError('seccion_no_disponible', 'La materia no muestra un enlace a esa sección de Brightspace.')

    async def listar_materias(self, limite=50, cursor=None):
        if cursor:
            return self.pages.next(cursor, 'materias', limite)
        self.pages.validate_limit(limite)
        page = await self.go(HOME)
        # The course card widget is hydrated after DOMContentLoaded.
        card = page.locator('#panel-search-my-enrollments')
        try:
            await card.wait_for(state='attached', timeout=self.settings.timeout_ms)
        except BrowserTimeout:
            raise AppError('interfaz_no_disponible', 'No se encontró Mis cursos. Revisá el ingreso o los cambios de interfaz.')
        try:
            await card.locator('a[href*="/d2l/home/"]').first.wait_for(state='visible', timeout=self.settings.timeout_ms)
        except BrowserTimeout:
            return self.pages.first([], 'materias', limite, complete=False)
        complete = await settled(page, self.settings.timeout_ms)
        found = {}
        for link in await links(card):
            if not re.fullmatch(r'/d2l/home/\d+', urlsplit(link['href']).path):
                continue
            name = link['text'].splitlines()[0].strip()
            if name:
                url = local_url(link['href'])
                ident = self.refs.add('materia', {'url':url, 'nombre':name})
                found[url] = {'id':ident, 'nombre':name, 'fuente':public_source(url)}
        # The home widget may show only pinned/filtered courses. Never claim all enrollments.
        result = self.pages.first(list(found.values()), 'materias', limite, complete=False)
        result['aviso'] = 'Se listan los cursos visibles de Mis cursos; puede haber filtros o cursos no mostrados.' if complete else 'Mis cursos sigue cargando; repetí el listado.'
        return result

    async def listar_tareas(self, materia_id: str, limite=50, cursor=None):
        self.refs.get(materia_id, 'materia')
        scope = 'tareas:'+materia_id
        if cursor:
            return self.pages.next(cursor, scope, limite)
        self.pages.validate_limit(limite)
        page = await self.course_page(materia_id, 'tareas')
        loaded = await settled(page, self.settings.timeout_ms)
        table = page.get_by_role('table', name=re.compile(r'asignaciones|assignments', re.I))
        if not await table.count():
            raise AppError('interfaz_no_disponible', 'No se encontró la tabla de Actividades; no se puede asegurar que esté vacía.')
        rows = await table.first.locator('tr').evaluate_all('''rows => rows.map(row => {
            const cells=[...row.querySelectorAll('td')];
            return {cells:cells.map(c=>c.innerText.trim()), links:cells.map(c=>[...c.querySelectorAll('a[href]')].map(a=>({href:a.href,text:a.innerText.trim()})))};
        }).filter(r=>r.cells.length>=2)''')
        items=[]
        for row in rows:
            cell = row['cells'][0]
            title = row['links'][0][0]['text'] if row['links'][0] else cell.splitlines()[0]
            date = re.search(r'(?:Vence el|Due(?: on)?)[^\n]+', cell, re.I)
            detail = next((a['href'] for group in row['links'] for a in group
                           if '/folder_submit_files.d2l' in a['href']), None)
            summary = {'titulo':title, 'estado':row['cells'][1],
                       'fecha_original':date.group(0) if date else None,
                       'puntuacion_visible':row['cells'][2] if len(row['cells'])>2 else None,
                       'materia_id':materia_id, 'fuente':public_source(detail or page.url)}
            ident = self.refs.add('tarea', {'url':local_url(detail) if detail else None, 'resumen':summary})
            items.append({'id':ident, **summary})
        return self.pages.first(items, scope, limite, complete=loaded and not await has_more(page))

    async def leer_tarea(self, tarea_id: str):
        ref = self.refs.get(tarea_id, 'tarea')
        if not ref['url']:
            return {'ok':True, **ref['resumen'], 'consigna':None, 'materiales':[], 'completo':False,
                    'aviso':'La actividad está cerrada o no muestra enlace a la consigna; se conserva solo el resumen visible.'}
        page = await self.go(ref['url'])
        expand = page.get_by_role('button', name=re.compile(r'^(Mostrar información de asignación|Show Assignment Information)$', re.I))
        if await expand.count() and await expand.first.is_visible():
            await expand.first.click()
        loaded = await settled(page, self.settings.timeout_ms)
        body = page.locator('#d_content_inner, .d_content_inner').first
        if not await body.count():
            body = page.locator('body')
        text, bounded = await bounded_text(body)
        start = re.search(r'Instrucciones|Instructions', text, re.I)
        end = re.search(r'Enviar asignación|Submit Assignment|Archivos para enviar', text, re.I)
        if start:
            instruction = text[start.end():end.start() if end else len(text)].strip()
            instruction = re.sub(r'\n(?:Enviar|Cancelar|Submit|Cancel)\s*$', '', instruction).strip()
        else:
            instruction = None
        materials=[]
        for link in await links(body):
            try:
                url=local_url(link['href'])
            except AppError:
                continue
            suffix=urlsplit(url).path.rsplit('.',1)[-1].lower()
            topic=bool(re.search(r'/d2l/le/content/\d+/viewContent/\d+/View',urlsplit(url).path,re.I))
            if suffix not in {'pdf','docx','pptx'} and not topic:
                continue
            kind=suffix if suffix in {'pdf','docx','pptx'} else document_kind(link['title']+' '+link['context'])
            resource={'url':url, 'nombre':link['text'], 'tipo':kind, 'materia_id':ref['resumen']['materia_id']}
            if not topic:
                resource['parent_url']=ref['url']
            ident=self.refs.add('archivo',resource)
            if not any(item['id']==ident for item in materials):
                materials.append({'id':ident,'nombre':link['text'],'tipo':kind,'fuente':public_source(url)})
        return {'ok':True, **ref['resumen'], 'consigna':instruction,
                'materiales':materials,
                'completo':bool(instruction) and loaded and bounded,
                'aviso':None if instruction and loaded and bounded else 'No se pudo recuperar toda la consigna de esta vista.'}

    async def leer_anuncios(self, materia_id: str, limite=10, cursor=None):
        course=self.refs.get(materia_id, 'materia')
        scope = 'anuncios:'+materia_id
        if cursor:
            return await self._news_details(self.pages.next(cursor, scope, limite))
        self.pages.validate_limit(limite)
        page = await self.course_page(materia_id, 'anuncios')
        loaded = await settled(page, self.settings.timeout_ms)
        items=[]
        articles = page.locator('article, .d2l-news-item, .d2l-widget-news-item')
        course_number=urlsplit(course['url']).path.rsplit('/',1)[1]
        for article in await articles.all():
            text, complete = await bounded_text(article, 10000)
            heading = article.get_by_role('heading').first
            title = (await heading.inner_text()).strip() if await heading.count() else text.splitlines()[0]
            item={'titulo':title, 'texto':text, 'texto_completo':complete, 'fuente':public_source(page.url)}
            for link in await links(article):
                if re.fullmatch(r'/d2l/le/news/'+re.escape(course_number)+r'/\d+/view',urlsplit(link['href']).path):
                    url=local_url(link['href'])
                    item.update(id=self.refs.add('anuncio',{'url':url}),texto_completo=False,fuente=public_source(url))
                    break
            items.append(item)
        # Some Brightspace versions use containers without a stable item class.
        if not items:
            for link in await links(page):
                if re.fullmatch(r'/d2l/le/news/'+re.escape(course_number)+r'/\d+/view', urlsplit(link['href']).path):
                    url=local_url(link['href'])
                    ident=self.refs.add('anuncio', {'url':url})
                    if not any(item.get('id')==ident for item in items):
                        items.append({'id':ident, 'titulo':link['text'], 'texto':link['context'], 'texto_completo':False, 'fuente':public_source(url)})
        empty = page.get_by_text(re.compile(r'No (?:hay|existen).*(?:noticias|anuncios)|No (?:news|announcements)', re.I))
        known_empty = any([await marker.is_visible() for marker in await empty.all()])
        result=self.pages.first(items, scope, limite, complete=loaded and (bool(items) or known_empty) and not await has_more(page))
        return await self._news_details(result)

    async def _news_details(self, result):
        for item in result['items']:
            if item.get('id') and not item['texto_completo']:
                try:
                    ref=self.refs.get(item['id'], 'anuncio')
                    page=await self.go(ref['url'])
                    loaded=await settled(page, self.settings.timeout_ms)
                    body=page.locator('#d_content_inner, .d_content_inner').first
                    if not await body.count():
                        body=page.locator('body')
                    text, complete=await bounded_text(body, 10000)
                    item['texto']=text
                    item['texto_completo']=loaded and complete
                except AppError:
                    item['aviso']='No se pudo abrir el anuncio; se conserva el resumen de la lista.'
        return result

    async def listar_archivos(self, materia_id: str, carpeta_id=None, limite=50, cursor=None):
        self.refs.get(materia_id, 'materia')
        folder = self.refs.get(carpeta_id, 'carpeta') if carpeta_id else None
        if folder and folder['materia_id'] != materia_id:
            raise AppError('referencia_invalida', 'La carpeta pertenece a otra materia.')
        scope = f'archivos:{materia_id}:{carpeta_id}'
        if cursor:
            return self.pages.next(cursor, scope, limite)
        self.pages.validate_limit(limite)
        page = await self.course_page(materia_id, 'archivos')
        if folder:
            anchor = page.locator('#ContentModuleTree a').filter(has=page.locator('[id="'+folder['tree_id']+'"]'))
            if await anchor.count()!=1:
                raise AppError('referencia_desactualizada', 'El módulo cambió o no está visible. Volvé a listar los materiales.')
            await anchor.click()
            await page.get_by_role('heading', name=folder['nombre'], exact=True).first.wait_for(state='visible', timeout=self.settings.timeout_ms)
            expand=page.get_by_role('button',name=re.compile(r'^(Expandir todo|Expand All)$',re.I))
            if await expand.count() and await expand.first.is_visible():
                await expand.first.click()
        loaded = await settled(page, self.settings.timeout_ms)
        tree = page.locator('#ContentModuleTree')
        if not await tree.count():
            raise AppError('interfaz_no_disponible', 'No se encontró el árbol de Contenido de Brightspace.')
        modules = await tree.locator('a').evaluate_all('''nodes=>nodes.map(a=>{
            const item=a.querySelector('[id^="TreeItem"]');
            return item ? {tree_id:item.id, nombre:(item.querySelector('.d2l-textblock')||item).innerText.split(' módulo:')[0].trim()} : null;
        }).filter(Boolean)''')
        items=[]
        if not folder:
            for module in modules:
                ident = self.refs.add('carpeta', {**module, 'materia_id':materia_id})
                items.append({'id':ident, 'nombre':module['nombre'], 'tipo':'carpeta', 'fuente':public_source(page.url)})
        for link in await links(page):
            if re.search(r'/d2l/le/content/\d+/viewContent/\d+/View', link['href'], re.I):
                kind = document_kind(link['title']+' '+link['context'])
                url = local_url(link['href'])
                ident = self.refs.add('archivo', {'url':url, 'nombre':link['text'], 'tipo':kind, 'materia_id':materia_id})
                if not any(x['id']==ident for x in items):
                    items.append({'id':ident, 'nombre':link['text'], 'tipo':kind, 'fuente':public_source(url)})
        return self.pages.first(items, scope, limite, complete=loaded and bool(folder) and not await has_more(page))

    async def leer_documento(self, archivo_id: str, cursor=None, limite_caracteres=10000):
        ref = self.refs.get(archivo_id, 'archivo')
        if ref['tipo'] not in {'pdf', 'docx', 'pptx', 'html'}:
            raise AppError('formato_no_soportado', 'Este recurso no es un documento admitido. No se abren cuestionarios, asignaciones, videos ni archivos ejecutables.')
        if isinstance(limite_caracteres, bool) or not isinstance(limite_caracteres, int) or not 1<=limite_caracteres<=10000:
            raise AppError('limite_invalido', 'El límite de texto debe estar entre 1 y 10000.')
        scope='texto:'+archivo_id
        if cursor:
            part=self.pages.next(cursor, scope, 1)
            cache=self.texts.get(part['items'][0]['cache'], 'texto')
            offset=part['items'][0]['offset']
            return self._text_result(cache, offset, limite_caracteres, scope)
        page=await self.go(ref.get('parent_url',ref['url']))
        await settled(page, self.settings.timeout_ms)
        if ref['tipo']=='html':
            deadline=asyncio.get_running_loop().time()+self.settings.timeout_ms/1000
            frames=[]
            while not frames:
                frames=[frame for frame in page.frames if frame is not page.main_frame and frame.url.startswith(HOME.split('/d2l')[0]+'/content/')]
                if frames:
                    break
                if asyncio.get_running_loop().time()>=deadline:
                    raise AppError('contenido_no_disponible', 'No se encontró la página de contenido; puede ser un recurso externo o no compatible.')
                await asyncio.sleep(.1)
            frame=frames[0]
            await frame.wait_for_load_state('domcontentloaded', timeout=self.settings.timeout_ms)
            local_url(frame.url)
            if not await settled(frame,self.settings.timeout_ms):
                raise AppError('contenido_no_disponible', 'La página de contenido sigue cargando; repetí la consulta.')
            text, complete = await bounded_text(frame.locator('body'), MAX_TEXT)
            data={'texto':text, 'extraccion_completa':complete, 'aviso':'Texto de la página; no incluye audio, video ni imágenes.'}
        else:
            from .downloads import read_download
            data=await read_download(self.browser, ref)
        if not data['texto'].strip():
            raise AppError('sin_texto', 'No se encontró texto extraíble en este recurso.')
        cache={**data, 'nombre':ref['nombre'], 'fuente':public_source(ref['url'])}
        return self._text_result(cache, 0, limite_caracteres, scope)

    def _text_result(self, cache, offset, limit, scope):
        chunk=text_page(cache['texto'], offset, limit)
        cursor=None
        if chunk['siguiente_offset'] is not None:
            key=self.texts.add('texto', cache)
            # Reuse signed, query-bound cursors without exposing offsets or URLs.
            result=self.pages.first([None, {'cache':key, 'offset':chunk['siguiente_offset']}], scope, 1)
            cursor=result['cursor']
        return {'ok':True, 'texto':chunk['texto'], 'cursor':cursor,
                'completo':chunk['completo'] and cache['extraccion_completa'],
                'extraccion_completa':cache['extraccion_completa'], 'nombre':cache['nombre'],
                'fuente':cache['fuente'], 'aviso':cache['aviso'], 'total_caracteres':chunk['total_caracteres']}
