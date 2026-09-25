#!/usr/bin/env bash
# Installed as /usr/bin/wd-hdd-unlocker. Elevates through polkit so the
# desktop shows its normal password prompt, then runs the real binary.
set -euo pipefail

BIN="/usr/libexec/wd-hdd-unlocker/wd-hdd-unlocker-bin"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wd-hdd-unlocker"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/launcher.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

fail() {
  echo "[$(ts)] ERROR: $1" >> "$LOG"
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="WD My Passport Linux Unlocker" --text="$1" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "WD My Passport Linux Unlocker" "$1" >/dev/null 2>&1 || true
  fi
  echo "$1" >&2
  exit 1
}

# Pass-through flags (--demo, --version, --help) never need root.
for arg in "$@"; do
  case "$arg" in
    --demo|--version|-h|--help) exec "$BIN" "$@" ;;
  esac
done

if [[ "$(id -u)" -eq 0 ]]; then
  exec "$BIN" "$@"
fi

[[ -x "$BIN" ]] || fail "The application binary is missing at $BIN. Reinstall the package."

ENV_ARGS=(
  DISPLAY="${DISPLAY:-}"
  XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
  XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-}"
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
)
POLICY="/usr/share/polkit-1/actions/com.github.titasdas.wd-hdd-unlocker.policy"

if command -v pkexec >/dev/null 2>&1; then
  rc=0
  if [[ -f "$POLICY" ]]; then
    # The packaged polkit action allows a GUI and keeps DISPLAY and XAUTHORITY,
    # so the binary can be run directly and the prompt shows the app's own message.
    echo "[$(ts)] launching via pkexec (policy action)" >> "$LOG"
    pkexec "$BIN" "$@" >> "$LOG" 2>&1 || rc=$?
  else
    echo "[$(ts)] launching via pkexec env" >> "$LOG"
    pkexec env "${ENV_ARGS[@]}" "$BIN" "$@" >> "$LOG" 2>&1 || rc=$?
  fi
  [[ $rc -eq 0 ]] && exit 0
  # 126 = user dismissed the prompt, 127 = not authorised. Nothing else to try.
  if [[ $rc -eq 126 || $rc -eq 127 ]]; then
    exit $rc
  fi
  echo "[$(ts)] pkexec exited $rc, trying sudo" >> "$LOG"
fi

if command -v sudo >/dev/null 2>&1; then
  if sudo -E env "${ENV_ARGS[@]}" "$BIN" "$@" >> "$LOG" 2>&1; then
    exit 0
  fi
  fail "Could not start with elevated privileges. See $LOG"
fi

fail "Neither pkexec nor sudo is available."
