import pytest
from brightspace_facultad_mcp.core import AppError, Settings, ProfileLease, ReferenceStore, Paginator, source_url, file_source_url


def test_profile_exclusive_and_reusable(tmp_path):
    first, second = ProfileLease(tmp_path), ProfileLease(tmp_path)
    first.acquire()
    try:
        with pytest.raises(AppError, match='perfil_ocupado'):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_settings_keep_data_outside_source(monkeypatch, tmp_path):
    monkeypatch.setenv('BRIGHTSPACE_MCP_DATA_DIR', str(tmp_path))
    settings = Settings.from_env()
    assert settings.profile == tmp_path / 'browser-profile'
    assert settings.max_file_bytes == 25 * 1024 * 1024


def test_references_reject_unknown_and_wrong_kind():
    refs = ReferenceStore()
    ident = refs.add('materia', {'name': 'Una materia'})
    assert 'Una materia' not in ident
    assert refs.get(ident, 'materia')['name'] == 'Una materia'
    with pytest.raises(AppError, match='referencia_invalida'):
        refs.get(ident, 'archivo')
    with pytest.raises(AppError):
        refs.get('https://evil.example', 'archivo')


def test_pagination_snapshot_bound_to_scope():
    pages = Paginator()
    first = pages.first(['a', 'b', 'c'], 'tareas:proximas', 2, complete=False)
    assert first['items'] == ['a', 'b']
    assert first['completo'] is False
    last = pages.next(first['cursor'], 'tareas:proximas', 2)
    assert last['items'] == ['c'] and last['cursor'] is None
    with pytest.raises(AppError, match='cursor_invalido'):
        pages.next(first['cursor'], 'archivos', 2)
    with pytest.raises(AppError):
        pages.next(first['cursor'] + 'x', 'tareas:proximas', 2)


@pytest.mark.parametrize('limit', [0, -1, 101])
def test_pagination_bounds(limit):
    with pytest.raises(AppError):
        Paginator().first([], 'x', limit)


def test_sources_remove_credentials_and_fragments():
    assert source_url('https://school.sharepoint.com/a.docx?token=SECRET#auth=SECRET') == 'https://school.sharepoint.com/a.docx'
    assert source_url('https://user:SECRET@school.sharepoint.com/a') == ''
    assert source_url('javascript:alert(1)') == ''


def test_file_source_retains_document_path_without_auth_query():
    value=file_source_url('https://school.sharepoint.com/sites/A/_layouts/15/filebrowser.aspx?id=%2Fsites%2FA%2FDocumentos%20del%20Curso&share=SECRET','Apunte uno.docx')
    assert value=='https://school.sharepoint.com/sites/A/Documentos%20del%20Curso/Apunte%20uno.docx'
    assert 'SECRET' not in value
