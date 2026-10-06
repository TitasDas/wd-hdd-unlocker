# Linux hardware tooling: notes from this project

## One drive, several device nodes

A single USB drive shows up as `/dev/sdX` (block device) and as one or more `/dev/sgX` (SCSI generic). They are different interfaces to the same hardware. A vendor command can fail on one and work on another, so the app tries each candidate.

## Read live state, not old logs

`dmesg` tells you what happened. `/sys` and udev tell you what is true now. Make runtime decisions from `/sys` and `udevadm`, and use kernel logs for debugging.

## Match devices by identity

Use udev properties such as `ID_PATH` and the USB vendor and product IDs to pair a disk with its control node. Two devices that look alike are not proof. If the match is ambiguous, stop and warn rather than guess.

## SCSI errors come from the device

`Check Condition` and `Illegal Request` are answers from the drive's firmware. They usually mean the command went to the wrong node, the bridge does not support it, or the password was wrong. They are rarely a UI bug.

## Root changes the environment

Unlock and mount need root. A GUI started as root inside a user session prints warnings (for example about `XDG_RUNTIME_DIR`). Most are harmless, but they can affect file dialogs and opening folders as the desktop user.

## Check that a mount worked

A zero exit code from `mount` is not enough. Confirm the target with `findmnt` and check the filesystem. If the desktop automounted somewhere unexpected, remount to a known path.

## Log enough to debug from a report

Log which node was chosen, which transport ran the command, and the decoded sense data on failure. "Failed" on its own forces a second round trip with the user.

## Testing system tools

Unit-test the deterministic parts: detection, node mapping and state transitions. Feed recorded command output in to cover failure paths. Keep real-hardware testing as a final manual step.

## Repo layout

Keep `app/`, `scripts/`, `docs/` and `tests/` separate. Keep entry points stable across refactors so launchers and docs do not break. An issue template gets you usable bug reports.

## Privacy in public repos

Do not commit local logs. Keep personal paths and serial numbers out of fixtures and docs. Ask reporters to redact anything sensitive.

## References

Linux:
- Kernel SCSI docs: https://docs.kernel.org/scsi/
- Sysfs overview: https://docs.kernel.org/filesystems/sysfs.html
- `man 7 udev`, `man 8 udevadm`, `man 8 lsblk`, `man 8 findmnt`, `man 8 mount`, `man 8 sg_raw`

Desktop and UI:
- GNOME Human Interface Guidelines: https://developer.gnome.org/hig/
- KDE Human Interface Guidelines: https://develop.kde.org/hig/
- freedesktop Desktop Entry Spec: https://specifications.freedesktop.org/desktop-entry-spec/latest/
- freedesktop Icon Theme Spec: https://specifications.freedesktop.org/icon-theme-spec/latest/
