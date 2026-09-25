# Safety Notes

- Back up important data before using any of the password or erase features.
- Erase resets the drive's encryption key. Nothing on the drive can be read afterwards, by anyone, with any tool. The app asks you to type ERASE and confirms once more; read both dialogs.
- A forgotten password cannot be recovered. Erase is the only way back to a usable drive.
- Removing the password leaves the data encrypted on the platters but lets any computer open the drive.
- Connect only the drive you intend to work on. When several WD drives are attached, check the model, size and masked serial in the drive selector before acting.
- The drive relocks only when it loses power. "Eject and lock" powers the USB port down; if that fails on your system the app tells you to unplug the drive.
- The app runs with root privileges. It only touches the WD drive you selected, its mount point, and (on request) the owner of that mount point's top folder.
- If an operation fails, stop and read the Activity page before retrying. Five wrong passwords in a row can make the drive refuse further attempts until it is unplugged.
- Launcher log for start-up problems: `~/.local/state/wd-hdd-unlocker/launcher.log`.
