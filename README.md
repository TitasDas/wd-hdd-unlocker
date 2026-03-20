# WD Security Unlocker

Linux desktop utility for unlocking compatible WD Security-protected drives and mounting them.
If you use WD My Passport drives on Linux and get stuck with a locked drive, this helps you unlock and mount it with a simple desktop app and CLI flow. It is aimed at Linux users who need practical access to their own WD-encrypted external drives.

Legal: unofficial utility, no WD affiliation, authorized-use only. See [DISCLAIMER](docs/DISCLAIMER.md).

## Screenshots
### Light Mode - Main
![Light mode main](assets/screenshot-light-main.png)

### Light Mode - Unlock Success
![Light mode success](assets/screenshot-light-success.png)

### Dark Mode - Main
![Dark mode main](assets/screenshot-dark-main.png)

### Dark Mode - Unlock Success
![Dark mode success](assets/screenshot-dark-success.png)

## What You Can Do
- Unlock a WD Security-protected drive using your password.
- Mount the drive after unlock.
- Run from terminal or desktop launcher.

## Quick Start
1. Install Python 3 and PyQt5.
2. Run `./scripts/build-linux.sh`.
3. Run `./scripts/install-desktop-entry.sh`.
4. Launch **WD Security Unlocker**.

## Credits
- Original upstream: https://github.com/KenMacD/wdpassport-utils
- GUI lineage includes work by: https://github.com/electronicsguy

Core docs:
- [NOTICE](NOTICE)
- [LICENSE](LICENSE)
- [TERMS](docs/TERMS.md)
- [LEGAL_USE](docs/LEGAL_USE.md)
- [TRADEMARKS](docs/TRADEMARKS.md)
- [SECURITY](docs/SECURITY.md)
- [CONTRIBUTING](docs/CONTRIBUTING.md)
- [SAFETY](docs/SAFETY.md)
- [RELEASE_CHECKLIST](docs/RELEASE_CHECKLIST.md)

## Canary
`CANARY:WDSU:20260320:R2B9K1`
