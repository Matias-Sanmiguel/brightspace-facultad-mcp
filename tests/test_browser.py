import time
import pytest
from brightspace_facultad_mcp.browser import BrowserSession
from brightspace_facultad_mcp.core import Settings, AppError

HOME = 'https://virtualbsp.uade.edu.ar/d2l/home'

async def test_status_does_not_open_browser(tmp_path):
    session = BrowserSession(Settings(tmp_path, headless=True))
    assert (await session.status())['estado'] == 'sin_iniciar'
    assert session.context is None

async def test_session_reuses_own_profile_and_excludes_other_processes(tmp_path):
    first = BrowserSession(Settings(tmp_path, headless=True))
    second = BrowserSession(Settings(tmp_path, headless=True))
    try:
        context = await first.start()
        await context.add_cookies([{'name':'fixture', 'value':'saved', 'url':HOME, 'expires':time.time()+3600}])
        with pytest.raises(AppError, match='perfil_ocupado'):
            await second.start()
        await first.close()
        context = await second.start()
        assert any(c['name']=='fixture' for c in await context.cookies())
        directory = second.download_dir
    finally:
        await first.close()
        await second.close()
    assert not directory.exists()

async def test_login_state_checks_origin_and_brightspace_navigation(page, tmp_path):
    session = BrowserSession(Settings(tmp_path, headless=True))
    html = '<a href="/d2l/home">Mis cursos</a><a href="/d2l/le/content/12/Home">Contenido</a>'
    await page.route('https://**/*', lambda route: route.fulfill(body=html, content_type='text/html'))
    await page.goto(HOME)
    assert await session.page_state(page) == 'conectado'
    await page.goto('https://evil.example/d2l/home')
    assert await session.page_state(page) != 'conectado'

async def test_institutional_login_form_is_not_authenticated(page, tmp_path):
    session = BrowserSession(Settings(tmp_path, headless=True))
    await page.route('https://**/*', lambda route: route.fulfill(body='<input type="password"><button>Ingresar</button>', content_type='text/html'))
    await page.goto(HOME)
    assert await session.page_state(page) == 'autenticacion_pendiente'

async def test_headless_login_is_actionable(tmp_path):
    with pytest.raises(AppError, match='modo_sin_ventana'):
        await BrowserSession(Settings(tmp_path, headless=True)).login()
