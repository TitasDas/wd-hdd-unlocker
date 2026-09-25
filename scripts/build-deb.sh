#!/usr/bin/env bash
# Package dist/wd-hdd-unlocker as a .deb with desktop entry, icon and polkit policy.
# Usage: scripts/build-deb.sh [version]   (version defaults to the one in the app)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BIN="dist/wd-hdd-unlocker"
[[ -x "$BIN" ]] || { echo "Run scripts/build-linux.sh first ($BIN missing)." >&2; exit 1; }
command -v dpkg-deb >/dev/null 2>&1 || { echo "dpkg-deb is required." >&2; exit 1; }

VERSION="${1:-$(python3 -c 'import sys; sys.path.insert(0, "app"); import wdpassport; print(wdpassport.VERSION)')}"
VERSION="${VERSION#v}"
ARCH="$(dpkg --print-architecture)"
PKG="wd-hdd-unlocker"
STAGE="build/deb/${PKG}_${VERSION}_${ARCH}"

rm -rf "$STAGE"
install -d "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/libexec/$PKG" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/polkit-1/actions" \
  "$STAGE/usr/share/doc/$PKG"

install -m 0755 "$BIN" "$STAGE/usr/libexec/$PKG/${PKG}-bin"
install -m 0755 packaging/wd-hdd-unlocker-launcher.sh "$STAGE/usr/bin/$PKG"
install -m 0644 packaging/wd-hdd-unlocker.desktop "$STAGE/usr/share/applications/$PKG.desktop"
install -m 0644 assets/wd-hdd-unlocker.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/$PKG.svg"
install -m 0644 packaging/com.github.titasdas.wd-hdd-unlocker.policy "$STAGE/usr/share/polkit-1/actions/"
install -m 0644 README.md NOTICE LICENSE "$STAGE/usr/share/doc/$PKG/"
install -m 0644 docs/DISCLAIMER.md docs/LEGAL_USE.md docs/TERMS.md docs/SAFETY.md "$STAGE/usr/share/doc/$PKG/"

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Titas Das <titas.das@gmail.com>
Depends: util-linux, udev, usbutils, parted, policykit-1
Recommends: udisks2, ntfs-3g, exfatprogs, sg3-utils
Homepage: https://github.com/TitasDas/wd-hdd-unlocker
Description: Unlock, mount and manage WD My Passport drives on Linux
 Unofficial desktop utility for WD My Passport, My Passport Ultra, easystore
 and Elements drives that use WD Security. Unlocks the drive with its
 password, mounts it for the logged-in user, sets, changes or removes the
 password, safely ejects (which relocks the drive) and can erase it.
 .
 Not affiliated with or endorsed by Western Digital.
CONTROL

cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
POSTINST
chmod 0755 "$STAGE/DEBIAN/postinst"

mkdir -p dist
OUT="dist/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT" >/dev/null
echo "Package built: $PROJECT_ROOT/$OUT"
echo "Install with: sudo apt install ./$OUT"
