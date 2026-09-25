#!/usr/bin/env bash
# Developer install: a per-user desktop entry that launches from this checkout.
# End users should install the .deb from the releases page instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$PROJECT_ROOT/scripts/wd-security-launcher.sh"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_FILE="$APPS_DIR/wd-hdd-unlocker.desktop"

mkdir -p "$APPS_DIR" "$ICON_DIR"
cp "$PROJECT_ROOT/assets/wd-hdd-unlocker.svg" "$ICON_DIR/wd-hdd-unlocker.svg"

sed -e "s|^Exec=.*|Exec=$LAUNCHER|" -e "s|^Icon=.*|Icon=$ICON_DIR/wd-hdd-unlocker.svg|" \
  "$PROJECT_ROOT/packaging/wd-hdd-unlocker.desktop" > "$DESKTOP_FILE"

chmod +x "$LAUNCHER"
chmod +x "$DESKTOP_FILE"

echo "Desktop entry installed: $DESKTOP_FILE"
echo "Launcher log: ~/.local/state/wd-hdd-unlocker/launcher.log"
