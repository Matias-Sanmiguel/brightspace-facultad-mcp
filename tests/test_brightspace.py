from urllib.parse import urlsplit
import pytest
from brightspace_facultad_mcp.brightspace import BrightspaceService
from brightspace_facultad_mcp.core import Settings, AppError

ORIGIN = 'https://virtualbsp.uade.edu.ar'
NAV = '<nav><a href="/d2l/home">Mis cursos</a><a href="/d2l/home/42">Inicio</a><a href="/d2l/le/content/42/Home">Contenido</a><a href="/d2l/lms/dropbox/dropbox.d2l?ou=42">Actividades</a><a href="/d2l/lms/news/main.d2l?ou=42">Noticias</a></nav>'
HOME = '''<h1>UADE</h1><h2>Mis cursos</h2><div id="panel-search-my-enrollments"><div id="cards"></div></div><script>
const root=document.querySelector('#cards').attachShadow({mode:'open'});
root.innerHTML='<a href="/d2l/home/42" aria-label="Programación, 2026_2C">Programación</a><a href="/d2l/home/43">Base de datos</a>';
</script>'''
TASKS = '''<h1>Actividades</h1><table aria-label="Lista de asignaciones para este curso"><tr><th>Asignación</th><th>Estado de avance</th><th>Puntuación</th></tr>
<tr><td><a href="/d2l/lms/dropbox/user/folder_submit_files.d2l?db=11&ou=42">Trabajo 1</a><p>Vence el 20 de noviembre de 2026 23:59</p></td><td>No enviado</td><td>- / 10</td></tr>
<tr><td>Trabajo cerrado<p>Vence el 1 de noviembre de 2026 23:59</p></td><td><a href="/d2l/lms/dropbox/user/folders_history.d2l?db=12&ou=42">1 material enviado</a></td><td>9 / 10</td></tr></table><select aria-label="Resultados por página"><option>20 por página</option></select>'''
CONTENT = '''<div id="ContentModuleTree"><a href="javascript:void(0)" onclick="document.querySelector('h1').textContent='Unidad 1'"><div id="TreeItem501">Unidad 1</div></a></div><div class="d2l_two_panel_selector_main"><h1>Contenido</h1><ul><li><a href="/d2l/le/content/42/viewContent/601/View" title="'Apunte' - Página web">Apunte</a><span>Página web</span></li><li><a href="/d2l/le/content/42/viewContent/602/View" title="'Examen' - Cuestionario">Examen</a><span>Cuestionario</span></li><li><a href="/d2l/le/content/42/viewContent/603/View" title="'Presentación' - Presentación de PowerPoint">Presentación</a></li></ul></div>'''

@pytest.fixture
async def service(page, tmp_path):
    svc = BrightspaceService(Settings(tmp_path, headless=True, timeout_ms=1200))
    async def respond(route):
        path = urlsplit(route.request.url).path
        if path == '/d2l/home':
            body = HOME
        elif 'folders_list' in path or path.endswith('/dropbox.d2l'):
            body = TASKS
        elif 'folder_submit_files' in path:
            body = '<div id="d_content_inner"><h1>Trabajo 1</h1><div>Instrucciones</div><p>Construir un modelo de datos.</p><button>Enviar</button></div>'
        elif path.endswith('/Home'):
            body = CONTENT
        elif '/viewContent/601/' in path:
            body = '<h1>Apunte</h1><iframe src="/content/enforced/42/apunte.html"></iframe>'
        elif path == '/content/enforced/42/apunte.html':
            return await route.fulfill(body='<main><h1>Diseño</h1><p>Texto del apunte con ñ y 中文.</p></main>', content_type='text/html; charset=utf-8')
        elif '/viewContent/603/' in path:
            body = '<h1>Presentación</h1><button onclick="location.href=\'/content/enforced/42/slides.pptx\'">Descargar</button>'
        elif '/news/' in path:
            body = '<div id="d_content_inner"><h1>Noticias</h1><article><h2><a href="/d2l/le/news/42/7/view">Entrega final</a></h2><p>Publicado 10 de noviembre de 2026</p><p>Traer el proyecto.</p></article></div>'
        else:
            body = '<h1>Programación</h1>'
        await route.fulfill(body=NAV+body, content_type='text/html; charset=utf-8')
    await page.route('https://virtualbsp.uade.edu.ar/**', respond)
    await page.goto(ORIGIN+'/d2l/home')
    svc.browser.context = page.context
    svc.browser.page = page
    yield svc
    # The page fixture owns the context; the service owns no browser process.
    svc.browser.context = None
    svc.browser.page = None

async def course(service):
    result = await service.call('listar_materias', limite=1)
    assert result['items'][0]['nombre'] == 'Programación'
    assert result['cursor']
    assert '42' not in result['items'][0]['id'].split('_')[0]
    return result['items'][0]['id']

async def test_courses_include_shadow_dom_and_pagination(service):
    result = await service.call('listar_materias', limite=1)
    assert result['items'][0]['nombre'] == 'Programación'
    last = await service.call('listar_materias', limite=1, cursor=result['cursor'])
    assert last['items'][0]['nombre'] == 'Base de datos'
    assert last['cursor'] is None

async def test_courses_wait_for_delayed_widget_hydration(service):
    html = NAV + '''<div id="panel-search-my-enrollments"></div><script>
    setTimeout(()=>document.querySelector('#panel-search-my-enrollments').innerHTML='<a href="/d2l/home/42">Curso demorado</a>', 200);
    </script>'''
    await service.browser.page.route('**/d2l/home',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    result=await service.call('listar_materias')
    assert result['items'][0]['nombre']=='Curso demorado'

async def test_tasks_preserve_closed_row_and_visible_deadline(service):
    result = await service.call('listar_tareas', materia_id=await course(service))
    assert [t['titulo'] for t in result['items']] == ['Trabajo 1','Trabajo cerrado']
    assert result['items'][0]['fecha_original'] == 'Vence el 20 de noviembre de 2026 23:59'
    assert result['items'][1]['estado'] == '1 material enviado'
    closed = await service.call('leer_tarea', tarea_id=result['items'][1]['id'])
    assert closed['completo'] is False
    assert closed['consigna'] is None

async def test_task_reads_instructions_without_submitting(service):
    tasks = await service.call('listar_tareas', materia_id=await course(service))
    task = await service.call('leer_tarea', tarea_id=tasks['items'][0]['id'])
    assert 'Construir un modelo de datos.' in task['consigna']
    assert 'Enviar' not in task['consigna']

async def test_task_expands_assignment_information_when_collapsed(service):
    tasks=await service.call('listar_tareas',materia_id=await course(service))
    html=NAV+'''<div id="d_content_inner"><h1>Trabajo 1</h1><button onclick="document.querySelector('#details').hidden=false;this.hidden=true">Mostrar información de asignación</button>
    <div hidden id="details">Instrucciones<p>Consigna inicialmente oculta.</p></div><h2>Enviar asignación</h2><button>Enviar</button></div>'''
    await service.browser.page.route('**/folder_submit_files.d2l?db=11&ou=42',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    result=await service.call('leer_tarea',tarea_id=tasks['items'][0]['id'])
    assert result['consigna']=='Consigna inicialmente oculta.'

async def test_task_reads_rich_instructions_inside_shadow_dom(service):
    tasks=await service.call('listar_tareas',materia_id=await course(service))
    html=NAV+'''<div id="d_content_inner"><h1>Trabajo 1</h1><label>Instrucciones</label><div id="rich"></div><h2>Enviar asignación</h2><button>Enviar</button></div><script>
    document.querySelector('#rich').attachShadow({mode:'open'}).innerHTML='<p>Consigna con componentes web.</p>';
    </script>'''
    await service.browser.page.route('**/folder_submit_files.d2l?db=11&ou=42',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    result=await service.call('leer_tarea',tarea_id=tasks['items'][0]['id'])
    assert result['consigna']=='Consigna con componentes web.'

async def test_task_attachment_can_be_passed_to_document_reader(service, tmp_path):
    import io
    from docx import Document
    tasks=await service.call('listar_tareas',materia_id=await course(service))
    html=NAV+'''<div id="d_content_inner"><h1>Trabajo 1</h1><label>Instrucciones</label><p>Completar la plantilla.</p><a href="/content/enforced/42/plantilla.docx">Plantilla.docx</a><h2>Enviar asignación</h2></div>'''
    await service.browser.page.route('**/folder_submit_files.d2l?db=11&ou=42',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    doc=Document();doc.add_paragraph('Campos de la plantilla');stream=io.BytesIO();doc.save(stream)
    await service.browser.page.route('**/plantilla.docx',lambda r:r.fulfill(body=stream.getvalue(),headers={'content-type':'application/octet-stream','content-disposition':'attachment; filename="plantilla.docx"'}))
    service.browser.download_dir=tmp_path
    task=await service.call('leer_tarea',tarea_id=tasks['items'][0]['id'])
    assert task['materiales'][0]['nombre']=='Plantilla.docx'
    result=await service.call('leer_documento',archivo_id=task['materiales'][0]['id'])
    assert 'Campos de la plantilla' in result['texto']

async def test_modules_read_html_and_reject_quiz_without_navigation(service):
    materia = await course(service)
    root = await service.call('listar_archivos', materia_id=materia)
    folder = next(x for x in root['items'] if x['tipo']=='carpeta')
    files = await service.call('listar_archivos', materia_id=materia, carpeta_id=folder['id'])
    doc = next(x for x in files['items'] if x['nombre']=='Apunte')
    result = await service.call('leer_documento', archivo_id=doc['id'], limite_caracteres=12)
    assert result['texto'].startswith('Diseño')
    assert result['cursor']
    tail = await service.call('leer_documento', archivo_id=doc['id'], cursor=result['cursor'])
    assert '中文' in tail['texto']
    quiz = next(x for x in files['items'] if x['nombre']=='Examen')
    before = service.browser.page.url
    with pytest.raises(AppError, match='formato_no_soportado'):
        await service.call('leer_documento', archivo_id=quiz['id'])
    assert service.browser.page.url == before

async def test_module_waits_for_selected_heading_and_new_topics(service):
    materia=await course(service)
    html=NAV+CONTENT.replace("document.querySelector('h1').textContent='Unidad 1'", "setTimeout(()=>{document.querySelector('.d2l_two_panel_selector_main').innerHTML='<h1>Unidad 1</h1><a href=&quot;/d2l/le/content/42/viewContent/777/View&quot; title=&quot;Documento PDF&quot;>Nuevo apunte</a>'},200)")
    await service.browser.page.route('**/content/42/Home',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    root=await service.call('listar_archivos',materia_id=materia)
    folder=next(x for x in root['items'] if x['tipo']=='carpeta')
    result=await service.call('listar_archivos',materia_id=materia,carpeta_id=folder['id'])
    assert [x['nombre'] for x in result['items']]==['Nuevo apunte']

async def test_loading_inside_content_frame_is_not_document_text(service):
    root=await service.call('listar_archivos',materia_id=await course(service))
    doc=next(x for x in root['items'] if x['nombre']=='Apunte')
    await service.browser.page.route('**/content/enforced/42/apunte.html',lambda r:r.fulfill(body='<p>Cargando...</p>',content_type='text/html; charset=utf-8'))
    with pytest.raises(AppError,match='contenido_no_disponible'):
        await service.call('leer_documento',archivo_id=doc['id'])

async def test_reference_and_cursor_scopes_checked_before_navigation(service):
    first = await service.call('listar_materias', limite=1)
    before = service.browser.page.url
    with pytest.raises(AppError, match='referencia_invalida'):
        await service.call('leer_tarea', tarea_id=first['items'][0]['id'])
    with pytest.raises(AppError, match='cursor_invalido'):
        await service.call('listar_tareas', materia_id=first['items'][0]['id'], cursor=first['cursor'])
    assert service.browser.page.url == before

async def test_announcements_return_article_content(service):
    result = await service.call('leer_anuncios', materia_id=await course(service))
    assert result['items'][0]['titulo']=='Entrega final'
    assert 'Traer el proyecto.' in result['items'][0]['texto']

async def test_news_table_reads_details_and_excludes_global_tutorial(service):
    materia=await course(service)
    html=NAV+'''<div id="d_content_inner"><h1>Noticias</h1><a href="/d2l/le/news/6606/725/view">Tutorial global</a><table><tr><th><a href="/d2l/le/news/42/7/view">Entrega final</a></th><td>10 de noviembre</td></tr></table></div>'''
    await service.browser.page.route('**/news/main.d2l?ou=42',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    await service.browser.page.route('**/le/news/42/7/view',lambda r:r.fulfill(body=NAV+'<div id="d_content_inner"><h1>Entrega final</h1><p>Consigna completa del anuncio.</p></div>',content_type='text/html; charset=utf-8'))
    result=await service.call('leer_anuncios',materia_id=materia)
    assert len(result['items'])==1
    assert 'Consigna completa del anuncio.' in result['items'][0]['texto']
    assert result['items'][0]['texto_completo']

async def test_news_article_with_read_more_fetches_full_detail(service):
    materia=await course(service)
    html=NAV+'<article><h2>Entrega final</h2><p>Resumen...</p><a href="/d2l/le/news/42/7/view">Leer más</a></article>'
    await service.browser.page.route('**/news/main.d2l?ou=42',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
    await service.browser.page.route('**/le/news/42/7/view',lambda r:r.fulfill(body=NAV+'<div id="d_content_inner"><h1>Entrega final</h1><p>Texto completo del anuncio.</p></div>',content_type='text/html; charset=utf-8'))
    result=await service.call('leer_anuncios',materia_id=materia)
    assert 'Texto completo del anuncio.' in result['items'][0]['texto']

async def test_hidden_empty_news_marker_does_not_claim_empty_success(service):
    materia=await course(service)
    await service.browser.page.route('**/news/main.d2l?ou=42',lambda r:r.fulfill(body=NAV+'<p hidden>No hay noticias</p>',content_type='text/html; charset=utf-8'))
    result=await service.call('leer_anuncios',materia_id=materia)
    assert not result['completo']

async def test_loading_news_is_never_reported_as_complete_empty(service):
    materia = await course(service)
    await service.browser.page.route('**/news/main.d2l?ou=42', lambda r:r.fulfill(body=NAV+'<div id="d_content_inner"><h1>Noticias</h1><p>Cargando...</p></div>'))
    result = await service.call('leer_anuncios', materia_id=materia)
    assert not result['completo']
    assert result['aviso']

async def test_foreign_redirect_is_rejected(service):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'Foreign page')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    materia = await course(service)
    await service.browser.page.route('**/dropbox/dropbox.d2l?ou=42', lambda r:r.fulfill(status=302, headers={'location':f'http://127.0.0.1:{server.server_port}/data'}))
    try:
        with pytest.raises(AppError, match='(origen_no_permitido|autenticacion_pendiente)'):
            await service.call('listar_tareas', materia_id=materia)
    finally:
        server.shutdown();server.server_close();thread.join()
