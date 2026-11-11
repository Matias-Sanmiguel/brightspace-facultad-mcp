import os
import sys
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def test_real_stdio_discovers_eight_tools_and_reports_unstarted(tmp_path):
    env = {**os.environ, 'PYTHONPATH': str(__import__('pathlib').Path('src').resolve()),
           'BRIGHTSPACE_MCP_DATA_DIR': str(tmp_path), 'BRIGHTSPACE_MCP_HEADLESS': '1'}
    parameters = StdioServerParameters(command=sys.executable, args=['-m','brightspace_facultad_mcp','serve'], env=env)
    async with Client(parameters, read_timeout_seconds=10) as client:
        listed = await client.list_tools()
        assert {t.name for t in listed.tools} == {
            'estado_conexion','iniciar_sesion','listar_materias','listar_tareas',
            'leer_tarea','leer_anuncios','listar_archivos','leer_documento'}
        result = await client.call_tool('estado_conexion')
        assert result.structured_content['estado'] == 'sin_iniciar'
        assert not result.is_error
        result = await client.call_tool('listar_tareas', {'materia_id':'invalid','limite':101})
        assert result.is_error
        result = await client.call_tool('iniciar_sesion')
        assert result.structured_content['error'] == 'modo_sin_ventana'


async def test_legacy_stdio_client_can_initialize_and_list_tools(tmp_path):
    # Most desktop clients still use the MCP 2025 session-based protocol.
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client
    parameters = StdioServerParameters(command=sys.executable,args=['-m','brightspace_facultad_mcp','serve'],
        env={**os.environ,'PYTHONPATH':str(__import__('pathlib').Path('src').resolve()),'BRIGHTSPACE_MCP_DATA_DIR':str(tmp_path)})
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            assert len(result.tools) == 8
