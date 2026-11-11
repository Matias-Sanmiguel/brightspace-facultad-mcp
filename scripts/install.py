"""Cross-platform installer. Needs only Python 3.11+ and Internet access."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIP_VERSION = '26.3'


def run(*args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, cwd=ROOT, **kwargs)


def main():
    if sys.version_info < (3, 11):
        raise SystemExit('Instalá Python 3.11 o posterior y volvé a ejecutar el instalador.')
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Creando entorno Python aislado...', flush=True)
        venv.EnvBuilder(with_pip=False).create(environment)
    probe = subprocess.run([str(python), '-m', 'pip', '--version'], capture_output=True)
    if probe.returncode:
        # Bootstrap pip from its verified official PyPI wheel. This also works on
        # Linux installations where ensurepip/python3-venv is not present.
        print('Instalando pip en el entorno aislado desde PyPI...', flush=True)
        with urllib.request.urlopen(f'https://pypi.org/pypi/pip/{PIP_VERSION}/json', timeout=30) as response:
            metadata = json.load(response)
        wheel = next(x for x in metadata['urls'] if x['filename'].endswith('py3-none-any.whl'))
        with urllib.request.urlopen(wheel['url'], timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != wheel['digests']['sha256']:
            raise SystemExit('La verificación de pip falló; no se ejecutó el archivo descargado.')
        with tempfile.TemporaryDirectory(prefix='brightspace-mcp-pip-') as temp:
            path = Path(temp) / wheel['filename']
            path.write_bytes(content)
            unpacked = Path(temp) / 'unpacked'
            with zipfile.ZipFile(path) as archive:
                archive.extractall(unpacked)
            env = {**os.environ, 'PYTHONPATH': str(unpacked)}
            run(python, '-m', 'pip', '--isolated', 'install', '--ignore-installed', '--no-deps', str(path), env=env)
    for lock in ('requirements.lock', 'requirements-build.lock'):
        run(python, '-m', 'pip', '--isolated', 'install', '--require-hashes', '-r', ROOT / lock)
    run(python, '-m', 'pip', '--isolated', 'install', '--no-deps', '--no-build-isolation', ROOT)
    run(python, '-m', 'playwright', 'install', 'chromium')
    config = subprocess.check_output([str(python), '-m', 'brightspace_facultad_mcp', 'config'], cwd=ROOT)
    (ROOT / 'mcp-config.json').write_bytes(config)
    print('\nInstalación lista. Tu configuración MCP está en:', ROOT / 'mcp-config.json')
    print('Primero iniciá sesión con:')
    print(f'"{python}" -m brightspace_facultad_mcp login')
    print('Para diagnosticar problemas:')
    print(f'"{python}" -m brightspace_facultad_mcp doctor')
    print('Si Chromium informa bibliotecas de sistema faltantes, seguí la sección Linux del README.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f'La instalación no terminó ({type(exc).__name__}). Revisá el mensaje anterior y el README.', file=sys.stderr)
        raise SystemExit(1)
