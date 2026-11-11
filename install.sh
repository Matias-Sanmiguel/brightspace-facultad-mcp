#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$SCRIPT_DIR/scripts/install.py"
fi
printf '%s\n' 'Instalá Python 3.11 o posterior y volvé a ejecutar este archivo.' >&2
exit 1
