"""CLI setup, interactive sign-in and stdio entrypoint."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

from playwright.async_api import async_playwright

from . import __version__
from .browser import BrowserSession
from .core import AppError, Settings


def emit(value: dict):
    print(json.dumps(value, ensure_ascii=False, indent=2))


async def doctor(settings: Settings) -> dict:
    async with async_playwright() as pw:
        executable = Path(pw.chromium.executable_path)
    return {'version': __version__, 'sistema': platform.system(), 'python': platform.python_version(),
            'python_compatible': sys.version_info >= (3, 11), 'chromium_instalado': executable.is_file(),
            'entorno_grafico': platform.system() != 'Linux' or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')),
            'directorio_datos': str(settings.data_dir), 'perfil_existente': settings.profile.exists(),
            'dependencias': {name: importlib.metadata.version(name) for name in ['mcp','playwright','python-docx','python-pptx','pypdf']},
            'siguiente_paso': 'Ejecutá login para autenticarte y config para obtener la configuración MCP.' if executable.is_file() else 'Ejecutá con este mismo Python: -m playwright install chromium'}


async def interactive_login(settings: Settings, timeout: int):
    session = BrowserSession(settings)
    try:
        emit(await session.login())
        print('Completá el inicio de sesión en la ventana de Microsoft. No cierres esta terminal.', file=sys.stderr)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = await session.status()
            if result['estado'] == 'conectado':
                emit(result)
                print('Sesión guardada. Se cerrará el navegador para liberar el perfil al MCP.', file=sys.stderr)
                return 0
            if result['estado'] == 'sin_iniciar':
                raise AppError('navegador_cerrado', 'Se cerró el navegador antes de completar el ingreso.')
            await asyncio.sleep(1)
        raise AppError('autenticacion_pendiente', 'No se completó el ingreso a tiempo. Podés repetir login; no se borró el perfil.')
    finally:
        await session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='MCP local para consultar Brightspace de la facultad')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('serve', help='Servidor MCP por stdio; configurarlo en tu cliente')
    sub.add_parser('config', help='Imprimir configuración estándar MCP con ruta absoluta')
    sub.add_parser('doctor', help='Comprobar Python, Chromium y directorio de datos')
    login = sub.add_parser('login', help='Iniciar sesión desde una terminal antes de conectar el MCP')
    login.add_argument('--timeout', type=int, default=300, choices=range(30, 1801), metavar='SEGUNDOS')
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.command == 'serve':
            from .server import create_server
            create_server(settings).run(transport='stdio')
        elif args.command == 'config':
            config = {'command': str(Path(sys.executable).absolute()), 'args': ['-m', 'brightspace_facultad_mcp', 'serve']}
            keys = ['BRIGHTSPACE_MCP_DATA_DIR', 'BRIGHTSPACE_MCP_HEADLESS']
            if platform.system() == 'Linux':
                keys += ['DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'XAUTHORITY']
            environment = {k: os.environ[k] for k in keys if k in os.environ}
            environment.setdefault('BRIGHTSPACE_MCP_HEADLESS', '1')
            if environment:
                config['env'] = environment
            emit({'mcpServers': {'brightspace-facultad': config}})
        elif args.command == 'doctor':
            result = asyncio.run(doctor(settings))
            emit(result)
            return 0 if result['chromium_instalado'] else 1
        elif args.command == 'login':
            return asyncio.run(interactive_login(settings, args.timeout))
    except AppError as exc:
        print(json.dumps(exc.result(), ensure_ascii=False), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cerrado; el perfil local se conserva.', file=sys.stderr)
        return 130
    return 0
