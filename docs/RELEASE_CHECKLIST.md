# Release Checklist

- Bump `VERSION` in `app/wdpassport/__init__.py` and add a section to `CHANGELOG.md`.
- `python3 -m unittest discover -s tests -t . -v` passes.
- `python3 app/wd-security.py --demo` opens and every page renders in both themes.
- On real hardware: unlock, copy a file in and out as the desktop user, eject and lock, reconnect and unlock again.
- If the password features changed: set, change and remove a password on a scratch drive, then unlock it with WD Security on Windows or macOS.
- Regenerate screenshots: `python3 app/wd-security.py --demo --screenshots assets`.
- `./scripts/build-linux.sh && ./scripts/build-deb.sh`; install the .deb on a clean machine and launch from the menu.
- Confirm attribution files are present: `NOTICE`, `LICENSE`, `TRADEMARKS`.
- Confirm legal/safety docs are current: `DISCLAIMER`, `LEGAL_USE`, `TERMS`, `SAFETY`.
- Confirm no secrets, serial numbers or personal paths are in the repo.
- Tag `vX.Y.Z` and push the tag; the workflow publishes the binary, the .deb and checksums.
