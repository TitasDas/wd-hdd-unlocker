---
name: Compatibility Report
about: Report WD model compatibility and unlock behavior on Linux
labels: compatibility, model-support
---

## Summary
- Distro + version:
- Kernel (`uname -r`):
- WD model label:
- Outcome: (success / unlock failed / mount issue)

## App Logs
Paste last 40 lines from **Status & Activity**.

## Diagnostics
Run and paste output (redact sensitive values):

```bash
lsusb
lsusb -v -d 1058:
udevadm info --query=property --name /dev/sdX
udevadm info --query=property --name /dev/sgY
lsblk -o NAME,MODEL,SERIAL,TRAN,TYPE,SIZE
```

## Notes
- Replace `sdX` and `sgY` with device names shown in app logs.
- Redact serial numbers and personal mount paths before posting.
