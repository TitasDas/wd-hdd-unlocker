# Changelog

## 2.0.1

- New product mark and app icon: a drive platter with a keyhole cut through to the edge. Used in the sidebar, the window icon, the desktop entry and the .deb. Construction and usage rules in docs/BRAND.md.

## 2.0.0

The app now covers the whole WD Security feature set instead of unlock only.

Added
- Mounting with the desktop user as owner, so files can be copied, moved and deleted after unlock. NTFS, exFAT and FAT get `uid`/`gid`/`umask` options; ext4 and similar get a "Give me write access" button.
- Eject and lock: unmount, then power the USB device off so the drive relocks.
- Set password with hint, change password, remove password. Hashing parameters and hint are written to the drive in the WD Security format.
- Format drive: new exFAT, NTFS or ext4 volume with a new name, keeping the password and key.
- Erase (encryption key reset) with typed confirmation and optional exFAT, NTFS or ext4 format.
- Password hint read from the drive and shown on the Unlock page.
- Drive selector for machines with more than one WD drive attached.
- Redesigned interface: sidebar navigation, drive overview, volumes table, activity log, diagnostics report, light and dark themes.
- `--demo` mode that runs the full UI against a simulated drive without root, and `--screenshots` to render every page.
- `wdctl.py` command line tool with status, unlock, mount, lock, set-password, change-password, remove-password, format and erase.
- Native `SG_IO` transport with decoded SCSI sense data, so "wrong password", "too many attempts" and "wrong state" are reported as such. `sg_raw` remains as a fallback.
- `.deb` package with desktop entry, icon, polkit policy and launcher. Release workflow runs the tests, smoke-tests the binary in demo mode and publishes the .deb.
- 102 tests covering the protocol, the operations, device helpers, transports, dialogs and the main window (run headless).
- Tests workflow on every push; the release workflow runs the same suite before building.

Changed
- Code split into a `wdpassport` package: protocol, transport, devices, manager, simulator, ui.
- Binary and desktop entry renamed to `wd-hdd-unlocker`; launcher log moved to `~/.local/state/wd-hdd-unlocker/`.
- `sg_raw` is no longer required.

## 1.0.1

- Rename release binaries to wd-hdd-unlocker.

## 1.0.0

- First release: unlock and mount, PyQt5 interface, PyInstaller binary.
