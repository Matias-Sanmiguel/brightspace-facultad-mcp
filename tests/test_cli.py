import json
import os
from pathlib import Path
import subprocess
import sys


def cli(*args):
    return subprocess.run([sys.executable,'-m','brightspace_facultad_mcp',*args],
        env={**os.environ,'PYTHONPATH':str(Path('src').resolve())},capture_output=True,text=True,timeout=15)


def test_config_uses_absolute_interpreter_and_no_credentials():
    result = cli('config')
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)['mcpServers']['brightspace-facultad']
    assert Path(config['command']).is_absolute()
    assert config['args'] == ['-m','brightspace_facultad_mcp','serve']
    assert 'token' not in result.stdout.lower()


def test_doctor_checks_installed_browser():
    result = cli('doctor')
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    assert info['python_compatible'] is True
    assert info['chromium_instalado'] is True


def test_config_preserves_linux_display_for_stdio_children(monkeypatch):
    monkeypatch.setenv('DISPLAY', ':42')
    if sys.platform.startswith('linux'):
        config = json.loads(cli('config').stdout)['mcpServers']['brightspace-facultad']
        assert config['env']['DISPLAY'] == ':42'


def test_generated_config_runs_mcp_headlessly_by_default(monkeypatch):
    monkeypatch.delenv('BRIGHTSPACE_MCP_HEADLESS', raising=False)
    config = json.loads(cli('config').stdout)['mcpServers']['brightspace-facultad']
    assert config['env']['BRIGHTSPACE_MCP_HEADLESS'] == '1'


def test_generated_config_preserves_explicit_visible_mode(monkeypatch):
    monkeypatch.setenv('BRIGHTSPACE_MCP_HEADLESS', '0')
    config = json.loads(cli('config').stdout)['mcpServers']['brightspace-facultad']
    assert config['env']['BRIGHTSPACE_MCP_HEADLESS'] == '0'
