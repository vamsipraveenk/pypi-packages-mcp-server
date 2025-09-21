#!/usr/bin/env bash
set -e
ROOT="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

# Prefer venv if present, else python3, else python
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

echo "[run] $PY -m mcp_server.server stdio"
exec "$PY" -m mcp_server.server stdio