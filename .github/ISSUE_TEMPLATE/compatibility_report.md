---
name: Compatibility report
about: A WD drive that is not recognised or does not unlock
title: 'Compatibility report: <model> on <distro>'
labels: compatibility, model-support
assignees: ''
---

## Environment
- Distro and version:
- Kernel (`uname -r`):
- App version (shown at the bottom of the sidebar):
- How the app was started (deb menu entry, standalone binary, source):

## Drive
- Model label printed on the drive:
- What the Drive page shows (status pill, cipher, control node):

## Diagnostics
Open the Advanced page, press "Copy diagnostics" and paste the report below. Serial numbers are masked automatically; check the text for anything else you would rather not share.

```
<paste here>
```

## Extra command output (optional)
```
lsusb -v -d 1058: 2>/dev/null | head -60
lsblk -o NAME,MODEL,TRAN,TYPE,SIZE,FSTYPE
```
