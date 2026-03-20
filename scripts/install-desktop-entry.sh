#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$PROJECT_ROOT/scripts/wd-security-launcher.sh"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/wd-security.desktop"

mkdir -p "$APPS_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=WD Security Unlocker
Comment=Unlock and mount WD Security drives
Exec=$LAUNCHER
Type=Application
Terminal=false
Categories=Utility;System;
StartupNotify=true
EOF

chmod +x "$LAUNCHER"
chmod +x "$DESKTOP_FILE"

echo "Desktop entry installed: $DESKTOP_FILE"
echo "If it fails, check log: ~/.local/state/wd-security/launcher.log"
