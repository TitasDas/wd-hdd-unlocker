#!/usr/bin/env bash
# Build the standalone binary with PyInstaller into dist/wd-hdd-unlocker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 not found. Install python3 or set PYTHON_BIN." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import PyInstaller' >/dev/null 2>&1; then
  echo "PyInstaller is not installed for $PYTHON_BIN. Try: $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import PyQt5.QtSvg' >/dev/null 2>&1; then
  echo "PyQt5 (with QtSvg) is not installed for $PYTHON_BIN. Try: $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi

rm -rf build dist

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --name wd-hdd-unlocker \
  --paths app \
  --hidden-import PyQt5.QtSvg \
  --collect-submodules wdpassport \
  app/wd-security.py

echo "Build complete: $PROJECT_ROOT/dist/wd-hdd-unlocker"
echo "Try it without hardware: $PROJECT_ROOT/dist/wd-hdd-unlocker --demo"
