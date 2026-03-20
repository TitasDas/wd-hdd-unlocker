#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_PATH="$PROJECT_ROOT/dist/wd-security"
SRC_PATH="$PROJECT_ROOT/app/wd-security.py"
LOG_BASE="${XDG_STATE_HOME:-$HOME/.local/state}"
LOG_DIR="$LOG_BASE/wd-security"
LOG_FILE="$LOG_DIR/launcher.log"

mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

notify_error() {
  local msg="$1"
  echo "[$(ts)] ERROR: $msg" >> "$LOG_FILE"
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="WD Security Unlocker" --text="$msg" >/dev/null 2>&1 || true
  fi
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "WD Security Unlocker" "$msg" >/dev/null 2>&1 || true
  fi
  echo "$msg"
}

CMD=()

if command -v python3 >/dev/null 2>&1 && python3 -c 'import PyQt5' >/dev/null 2>&1; then
  CMD=(python3 "$SRC_PATH")
elif [[ -x "$BIN_PATH" ]]; then
  CMD=("$BIN_PATH")
else
  notify_error "No runnable app found. Install python3 + PyQt5 or run ./scripts/build-linux.sh first."
  exit 1
fi

echo "[$(ts)] Launch command: ${CMD[*]}" >> "$LOG_FILE"

if command -v pkexec >/dev/null 2>&1; then
  if pkexec env \
    DISPLAY="${DISPLAY:-}" \
    XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" \
    QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}" \
    "${CMD[@]}" >> "$LOG_FILE" 2>&1; then
    exit 0
  fi
  echo "[$(ts)] pkexec launch failed, attempting sudo fallback" >> "$LOG_FILE"
fi

if command -v sudo >/dev/null 2>&1; then
  if sudo -E "${CMD[@]}" >> "$LOG_FILE" 2>&1; then
    exit 0
  fi
  notify_error "Failed to launch via sudo. See: $LOG_FILE"
  exit 1
fi

notify_error "Neither pkexec nor sudo is available. Cannot run with required root permissions."
exit 1
