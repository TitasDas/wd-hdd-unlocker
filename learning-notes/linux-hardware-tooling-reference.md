# Linux Hardware Tooling: Practical Learning Notes

This note captures what we learned while building and debugging the WD unlock utility on Linux.

## 1) Know Your Device Nodes
- `/dev/sdX` is the block disk view.
- `/dev/sgX` is the SCSI generic command path.
- Vendor commands may work on one node and fail on another.
- Always log exactly which node you sent commands to.

## 2) Prefer Live Kernel State Over Logs
- `dmesg` is history, not current truth.
- For live detection, use `sysfs` and `udev` first.
- Example: `/sys/class/scsi_generic/*/device/type` for SCSI type.
- This avoids stale or wrong candidates.

## 3) Use Udev for Stable Identity
- `udevadm info --query=property --name /dev/...` gives stable metadata.
- `ID_PATH` is useful to match the disk and SG endpoint on the same USB path.
- Match by path before trying unlock commands.
- Path matching reduces wrong-endpoint failures.

## 4) Read SCSI Errors Correctly
- `Check Condition` means command-level failure from device firmware.
- `Illegal Request` means endpoint/command rejection.
- This is often not a GUI bug.
- Common causes: interface mismatch, unsupported firmware path, password/key mismatch for that command path.

## 5) Handle Multiple Devices Safely
- Multiple similar devices create ambiguity fast.
- If selection is ambiguous, stop and warn instead of guessing.
- Disable risky actions until one clear target remains.
- Safety beats convenience for disk/security tooling.

## 6) Build Candidate Lists in Layers
- First try strongest match (same USB path + expected SCSI type).
- Then try mapped fallback candidates.
- Then controlled last-resort fallbacks.
- Log candidate order so failures are diagnosable.

## 7) Mounting on Linux Needs Validation
- “Mounted” does not always mean usable from desktop.
- Validate with `findmnt` and check target path exists as a directory.
- Recover from broken automount paths by remounting to a safe known path.
- Keep mount behavior deterministic.

## 8) Root + Desktop Context Has Tradeoffs
- Disk unlock/mount generally needs root privileges.
- GUI via `pkexec`/`sudo` can show runtime warnings.
- Not all warnings are fatal, but they matter for UX.
- Keep launcher logs and visible error messages.

## 9) Make Errors Actionable
- Avoid generic “failed” popups only.
- Include endpoint, command path, and key SCSI detail in logs.
- Keep user-facing hints technically accurate.
- Good diagnostics reduce support time dramatically.

## 10) Test What You Can, Simulate What You Can’t
- Unit-test deterministic logic: detection, mapping, state handling.
- Add simulated end-to-end flows with mocks for command outputs.
- Use smoke tests for UI initialization and flow wiring.
- Real hardware unlock still needs on-device verification.

## 11) Organize Repo for Long-Term Maintainability
- Keep code in `app/`, scripts in `scripts/`, docs in `docs/`, tests in `tests/`.
- Keep backward-compatible wrappers when restructuring paths.
- Add issue templates for standardized diagnostics.
- Clear structure improves contributions and debugging speed.

## 12) Privacy and OSS Hygiene
- Never commit local launcher logs.
- Remove personal-looking paths from fixtures and screenshots.
- Ask users to redact serials and personal mount paths in reports.
- Document exactly what to share for compatibility reports.

## Quick Command Set (Daily Use)
```bash
# Run app launcher
./scripts/wd-security-launcher.sh

# Build binary
./scripts/build-linux.sh

# Install desktop entry
./scripts/install-desktop-entry.sh

# Run tests
python3 -m unittest -v tests/test_core_logic.py tests/test_user_flows.py
```

## Core Mindset
- Treat Linux hardware tooling as systems engineering, not just app UI work.
- Trust live device state, not assumptions.
- Prioritize safe defaults, observability, and reproducibility.
