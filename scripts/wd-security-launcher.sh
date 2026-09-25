#!/usr/bin/env bash
# Developer launcher: runs the app from this checkout with elevated privileges.
# Prefers the source tree (python3 + PyQt5), falls back to dist/wd-hdd-unlocker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_PATH="$PROJECT_ROOT/dist/wd-hdd-unlocker"
SRC_PATH="$PROJECT_ROOT/app/wd-security.py"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wd-hdd-unlocker"
LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

notify_error() {
  echo "[$(ts)] ERROR: $1" >> "$LOG_FILE"
  command -v zenity >/dev/null 2>&1 && zenity --error --title="WD My Passport Linux Unlocker" --text="$1" >/dev/null 2>&1 || true
  command -v notify-send >/dev/null 2>&1 && notify-send "WD My Passport Linux Unlocker" "$1" >/dev/null 2>&1 || true
  echo "$1" >&2
}

CMD=()
if command -v python3 >/dev/null 2>&1 && python3 -c 'import PyQt5.QtSvg' >/dev/null 2>&1; then
  CMD=(python3 "$SRC_PATH")
elif [[ -x "$BIN_PATH" ]]; then
  CMD=("$BIN_PATH")
else
  notify_error "No runnable app found. Install python3 + PyQt5 (pip install -r requirements.txt) or run scripts/build-linux.sh."
  exit 1
fi

for arg in "$@"; do
  case "$arg" in
    --demo|--version|-h|--help) exec "${CMD[@]}" "$@" ;;
  esac
done

echo "[$(ts)] Launch command: ${CMD[*]} $*" >> "$LOG_FILE"

ENV_ARGS=(
  DISPLAY="${DISPLAY:-}"
  XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
  WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}"
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}"
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
)

if command -v pkexec >/dev/null 2>&1; then
  if pkexec env "${ENV_ARGS[@]}" "${CMD[@]}" "$@" >> "$LOG_FILE" 2>&1; then
    exit 0
  fi
  rc=$?
  [[ $rc -eq 126 || $rc -eq 127 ]] && exit $rc
  echo "[$(ts)] pkexec exited $rc, attempting sudo fallback" >> "$LOG_FILE"
fi

if command -v sudo >/dev/null 2>&1; then
  if sudo -E env "${ENV_ARGS[@]}" "${CMD[@]}" "$@" >> "$LOG_FILE" 2>&1; then
    exit 0
  fi
  notify_error "Failed to launch via sudo. See: $LOG_FILE"
  exit 1
fi

notify_error "Neither pkexec nor sudo is available. Cannot run with required root permissions."
exit 1
