## 1) Linux exposes hardware through multiple interfaces
- One physical drive can appear as `/dev/sdX` and `/dev/sgX`.
- They are different interfaces, not duplicates.
- A command may fail on one and work on the other.

## 2) Live system state beats logs
- `dmesg` is historical context, not a current source of truth.
- For runtime decisions, prefer `sysfs` and `udev`.
- Rule: detect from live files in `/sys`, not old kernel messages.

## 3) Device identity must be explicit
- Use udev properties (`ID_PATH`, model/product IDs) to map the right endpoint.
- "Looks similar" is not enough when multiple USB devices exist.
- If ambiguous, stop and warn instead of guessing.

## 4) SCSI errors are protocol-level signals
- `Check Condition` and `Illegal Request` come from device firmware.
- That usually means command-path mismatch, unsupported behavior, or key/password mismatch.
- It is often not a UI bug.

## 5) Root context changes behavior
- Storage unlock/mount operations often require elevated privileges.
- Root-run GUI in user sessions can produce environment warnings.
- Warnings are not always fatal, but they matter for reliability and UX.

## 6) Mount success needs verification
- “Mounted” is not enough.
- Verify actual target path with `findmnt` and filesystem checks.
- Recover from invalid automount targets by remounting to a known safe path.

## 7) Good Linux tools are observable
- Log candidate selection, command path, and exact failure reason.
- Generic “failed” messages slow debugging.
- Good logs turn support into engineering.

## 8) Test strategy for system tools
- Unit-test deterministic logic (detection, mapping, state transitions).
- Simulate command outputs for failure/success paths.
- Keep real hardware tests as a separate final validation step.

## 9) Maintainability is part of Linux engineering
- Keep clear repo boundaries: `app/`, `scripts/`, `docs/`, `tests/`.
- Keep command entrypoints stable when refactoring.
- Standardized issue templates improve triage quality.

## 10) Privacy hygiene matters in OSS
- Don’t commit local logs.
- Don’t leak personal paths/serials in fixtures or docs.
- Ask users to redact sensitive fields in reports.

## Linux References
- Kernel SCSI docs: https://docs.kernel.org/scsi/
- Sysfs overview: https://docs.kernel.org/filesystems/sysfs.html
- udev man page: `man 7 udev`
- udevadm man page: `man 8 udevadm`
- lsblk man page: `man 8 lsblk`
- findmnt man page: `man 8 findmnt`
- mount man page: `man 8 mount`
- sg_raw man page: `man 8 sg_raw`

## Linux Desktop/UI Design References
- GNOME Human Interface Guidelines: https://developer.gnome.org/hig/
- KDE Human Interface Guidelines: https://develop.kde.org/hig/
- freedesktop Desktop Entry Spec: https://specifications.freedesktop.org/desktop-entry-spec/latest/
- freedesktop Icon Theme Spec: https://specifications.freedesktop.org/icon-theme-spec/latest/

## Mindset based takeaway
- Treat Linux app + hardware work as systems engineering.
- Prefer correctness and observability over clever shortcuts.
- Build safe defaults first, then optimize UX.
