"""Local configuration, exclusive profile ownership and opaque result references."""
from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import urlsplit, urlunsplit, parse_qs, quote

from filelock import FileLock, Timeout
from platformdirs import user_data_path


class AppError(Exception):
    def __init__(self, code: str, message: str, **details: Any):
        self.code, self.message, self.details = code, message, details
        super().__init__(f'{code}: {message}')

    def result(self) -> dict:
        return {'ok': False, 'error': self.code, 'mensaje': self.message, **self.details}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    headless: bool = False
    timeout_ms: int = 30000
    max_file_bytes: int = 25 * 1024 * 1024
    scan_rounds: int = 20

    @property
    def profile(self) -> Path:
        return self.data_dir / 'browser-profile'

    @classmethod
    def from_env(cls) -> Settings:
        root = os.environ.get('BRIGHTSPACE_MCP_DATA_DIR')
        return cls(
            Path(root).expanduser().resolve() if root else user_data_path('brightspace-facultad-mcp', appauthor=False),
            headless=os.environ.get('BRIGHTSPACE_MCP_HEADLESS', '0') == '1',
        )


class ProfileLease:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = FileLock(str(data_dir / 'browser-profile.lock'))

    def acquire(self) -> None:
        try:
            self.lock.acquire(timeout=0)
        except Timeout as exc:
            raise AppError('perfil_ocupado', 'Otro proceso usa el perfil. Cerrá el comando login u otro cliente MCP y reintentá.') from exc

    def release(self) -> None:
        if self.lock.is_locked:
            self.lock.release()


class ReferenceStore:
    """References intentionally expire on server restart; they never contain URLs."""
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self._items: OrderedDict[str, tuple[str, dict]] = OrderedDict()

    def add(self, kind: str, value: dict) -> str:
        for key, entry in self._items.items():
            if entry == (kind, value):
                self._items.move_to_end(key)
                return key
        key = f'{kind}_{secrets.token_urlsafe(12)}'
        self._items[key] = (kind, value.copy())
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return key

    def get(self, key: str, kind: str) -> dict:
        entry = self._items.get(key)
        if entry is None or entry[0] != kind:
            raise AppError('referencia_invalida', 'Volvé a listar el recurso; el identificador no existe, venció o pertenece a otro tipo.')
        self._items.move_to_end(key)
        return entry[1].copy()


class Paginator:
    def __init__(self):
        self._secret = secrets.token_bytes(32)
        self._snapshots: OrderedDict[str, tuple[str, list, bool]] = OrderedDict()

    @staticmethod
    def validate_limit(limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise AppError('limite_invalido', 'El límite debe estar entre 1 y 100.')

    def _cursor(self, key: str, offset: int) -> str:
        payload = f'{key}:{offset}'.encode()
        tag = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(payload + b':' + tag.encode()).decode()

    def _page(self, key: str, offset: int, limit: int) -> dict:
        _, items, complete = self._snapshots[key]
        end = min(offset + limit, len(items))
        return {'ok': True, 'items': items[offset:end], 'cursor': self._cursor(key, end) if end < len(items) else None,
                'completo': complete and end == len(items), 'total_recuperado': len(items),
                'aviso': None if complete else 'La interfaz puede contener más elementos; no se garantiza una lista completa.'}

    def first(self, items: list, scope: str, limit: int = 50, complete: bool = True) -> dict:
        self.validate_limit(limit)
        key = secrets.token_urlsafe(12)
        self._snapshots[key] = (scope, list(items), complete)
        if len(self._snapshots) > 64:
            self._snapshots.popitem(last=False)
        return self._page(key, 0, limit)

    def next(self, cursor: str, scope: str, limit: int = 50) -> dict:
        self.validate_limit(limit)
        try:
            if len(cursor) > 512:
                raise ValueError
            key, raw_offset, tag = base64.b64decode(cursor, altchars=b'-_', validate=True).decode().split(':')
            payload = f'{key}:{raw_offset}'.encode()
            expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(tag, expected) or self._snapshots[key][0] != scope:
                raise ValueError
            offset = int(raw_offset)
            if not 0 < offset < len(self._snapshots[key][1]):
                raise ValueError
            return self._page(key, offset, limit)
        except (ValueError, KeyError, UnicodeError) as exc:
            raise AppError('cursor_invalido', 'El cursor no corresponde a esta consulta o venció. Repetí el listado sin cursor.') from exc


def source_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            return ''
        return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
    except ValueError:
        return ''


def file_source_url(value: str, name: str) -> str:
    """Build a usable file link from SharePoint's observed folder UI location."""
    safe=source_url(value)
    if not safe:
        return ''
    parts=urlsplit(value)
    folder=parse_qs(parts.query).get('id',[''])[0]
    if ((parts.hostname or '').endswith('.sharepoint.com') and folder.startswith('/')
            and not folder.startswith('//') and '..' not in folder.split('/')
            and '/' not in name and '\\' not in name and name not in {'.','..'}):
        path=quote(folder.rstrip('/'),safe='/')+'/'+quote(name,safe='')
        return urlunsplit((parts.scheme,parts.netloc,path,'',''))
    return safe
