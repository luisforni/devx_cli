#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
LOGO_FILE="$PROJECT_ROOT/scripts/logo_ascii.txt"
HELP_FILE="$PROJECT_ROOT/scripts/post_run_help.txt"

if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi

UNAME="$(uname -s || echo unknown)"
case "$UNAME" in
  Linux*)   OS=linux ;;
  Darwin*)  OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=win ;;
  *)        OS=unknown ;;
esac

if [[ ! -d "$VENV_DIR" ]]; then
  echo "→ Creating virtualenv at .venv ..."
  "$PY" -m venv "$VENV_DIR"
fi

if [[ "$OS" == "win" ]]; then
  [[ -f "$VENV_DIR/Scripts/activate" ]] && source "$VENV_DIR/Scripts/activate" || true
else
  source "$VENV_DIR/bin/activate"
fi

python -m pip install --upgrade pip >/dev/null
[[ -f "$REQ_FILE" ]] && pip install -r "$REQ_FILE" >/dev/null

clear || true
[[ -f "$LOGO_FILE" ]] && cat "$LOGO_FILE" && echo
[[ -f "$HELP_FILE" ]] && cat "$HELP_FILE" && echo

if [[ $# -eq 0 ]]; then
  exit 0
fi

python -m devx "$@"
