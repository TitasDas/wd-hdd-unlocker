"""High-level drive operations, independent of any UI toolkit.

`DriveManager` composes the protocol, a SCSI transport and the Linux plumbing
in `devices`. Every operation logs what it does through a callback so the UI
can show an activity trail, and raises `OperationError` with a message meant
for the person at the keyboard.
"""

import time

from . import devices as default_system
from . import protocol
from .transport import ChainedTransport, ScsiError, TransportUnavailable


class OperationError(Exception):
    """A user-facing failure. The message is safe to show in a dialog."""


class DriveState:
    """Everything the UI needs to know about one drive."""

    def __init__(self, drive, status=None, block=None, error=''):
        self.drive = drive
        self.status = status
        self.block = block
        self.error = error

    @property
    def hint(self):
        return self.block.hint if self.block else ''

    @property
    def supported(self):
        return self.status is not None


class DriveManager:
    def __init__(self, transport=None, system=None, log=None):
        self.transport = transport or ChainedTransport()
        self.system = system or default_system
        self._log = log or (lambda msg: None)
        self.user = self.system.desktop_user()

    def set_logger(self, log):
        self._log = log or (lambda msg: None)

    def log(self, msg):
        self._log(msg)

    # --- discovery ------------------------------------------------------------

    def scan(self):
        """Find WD drives and probe their security status."""
        states = []
        usb = self.system.wd_usb_present()
        disks = self.system.find_wd_disks()
        if not disks:
            if usb:
                self.log('A WD USB device is attached but no disk node was found yet. Give it a moment and refresh.')
            else:
                self.log('No WD USB device attached.')
            return states
        for disk in disks:
            drive = self.system.describe_drive(disk)
            states.append(self.probe(drive))
        return states

    def probe(self, drive):
        """Find the node that answers WD security commands and read the status."""
        last_error = ''
        for node in drive.sg_candidates or [drive.node]:
            try:
                data = self.transport.execute(node, protocol.cdb_encryption_status(), data_in_len=protocol.STATUS_ALLOC_LEN)
                status = protocol.parse_encryption_status(data)
            except (ScsiError, TransportUnavailable, protocol.ProtocolError) as exc:
                last_error = '%s: %s' % (node, exc)
                continue
            drive.control_node = node
            block = self._read_security_block(drive)
            self.log('%s (%s): %s, %s, control node %s' % (
                drive.display_name, drive.node, status.security_name, status.cipher_name, node))
            return DriveState(drive, status, block)
        self.log('%s (%s) did not answer WD security commands. Last error: %s' % (drive.display_name, drive.node, last_error))
        return DriveState(drive, error=last_error or 'no response')

    def refresh(self, state):
        drive = self.system.describe_drive(state.drive.disk)
        if state.drive.control_node:
            drive.control_node = state.drive.control_node
            if drive.control_node not in drive.sg_candidates:
                drive.sg_candidates.insert(0, drive.control_node)
            else:
                drive.sg_candidates.remove(drive.control_node)
                drive.sg_candidates.insert(0, drive.control_node)
        return self.probe(drive)

    def status(self, drive):
        data = self._exec(drive, protocol.cdb_encryption_status(), data_in_len=protocol.STATUS_ALLOC_LEN)
        return protocol.parse_encryption_status(data)

    def _read_security_block(self, drive):
        try:
            data = self.transport.execute(drive.control_node, protocol.cdb_read_handy_store(protocol.SECURITY_BLOCK),
                                          data_in_len=protocol.HANDY_BLOCK_SIZE)
            return protocol.parse_security_block(data)
        except (ScsiError, TransportUnavailable) as exc:
            self.log('Could not read the security block (%s); using WD defaults for hashing.' % exc)
            return None
        except protocol.ProtocolError as exc:
            self.log('Security block on the drive is damaged (%s); using WD defaults for hashing.' % exc)
            return None

    def _write_security_block(self, drive, block):
        data = protocol.build_security_block(block)
        self._exec(drive, protocol.cdb_write_handy_store(protocol.SECURITY_BLOCK), data_out=data)

    def _exec(self, drive, cdb, data_out=None, data_in_len=0):
        node = drive.control_node
        if not node:
            raise OperationError('This drive did not answer WD security commands. Reconnect it and refresh.')
        try:
            return self.transport.execute(node, cdb, data_out=data_out, data_in_len=data_in_len)
        except TransportUnavailable as exc:
            raise OperationError('Cannot talk to %s: %s' % (node, exc))

    # --- unlock and mount -------------------------------------------------------

    def unlock(self, state, password):
        drive = state.drive
        if not password:
            raise OperationError('Enter the drive password.')
        status = self.status(drive)
        if status.security == protocol.STATUS_LOCKED_BLOCKED:
            raise OperationError('The drive has blocked further unlock attempts. Unplug it, plug it back in and try again.')
        if status.is_accessible:
            self.log('Drive is already unlocked.')
            return self.mount(state)
        if status.security != protocol.STATUS_LOCKED:
            raise OperationError('Unexpected drive state: %s.' % status.security_name)
        block = state.block or protocol.SecurityBlock()
        if status.cipher in protocol.AES128_CIPHERS:
            self.log('This drive uses AES-128. The vendor password algorithm for AES-128 is not public, so unlock may not work.')
        length = protocol.password_blob_length(status)
        blob = protocol.derive_password_blob(password, block, length)
        param = protocol.build_unlock_param(blob)
        self.log('Sending unlock command to %s' % drive.control_node)
        try:
            self._exec(drive, protocol.cdb_unlock(len(param)), data_out=param)
        except ScsiError as exc:
            if protocol.is_wrong_password(exc.sense):
                raise OperationError('Wrong password. Check Caps Lock and try again.')
            if protocol.is_attempts_blocked(exc.sense):
                raise OperationError('Too many failed attempts. Unplug the drive, plug it back in and try again.')
            raise OperationError('Unlock failed: %s' % exc)
        after = self.status(drive)
        if not after.is_accessible:
            raise OperationError('The drive accepted the command but still reports %s.' % after.security_name)
        self.log('Drive unlocked.')
        return self.mount(state)

    def mount(self, state):
        """Expose the partitions to the desktop user. Returns the list of mount points."""
        drive = state.drive
        new_disk = self.system.rescan_disk(drive.disk, self.log)
        if new_disk != drive.disk:
            self.log('Drive re-enumerated as /dev/%s' % new_disk)
            drive = self.system.describe_drive(new_disk)
            drive.control_node = ''
            state.drive = drive
        parts = self.system.wait_for_automount(drive.disk)
        drive.partitions = parts
        if not parts:
            raise OperationError('The drive is unlocked but no partitions were found. It may need to be formatted (see Advanced).')
        targets = []
        for part in parts:
            if part.mountpoint:
                self.log('%s is already mounted at %s' % (part.node, part.mountpoint))
                targets.append(part.mountpoint)
                continue
            if not part.fstype:
                self.log('%s has no recognisable filesystem; skipping.' % part.node)
                continue
            try:
                target = self.system.mount_partition(part, self.user, self.log)
            except RuntimeError as exc:
                # The desktop automounter may have won the race while we were busy.
                target = self.system.mount_target(part.node)
                if not target:
                    self.log(str(exc))
                    continue
                self.log('%s was mounted by the desktop at %s' % (part.node, target))
            part.mountpoint = target
            targets.append(target)
        if not targets:
            raise OperationError('The drive is unlocked but nothing could be mounted. See the activity log for details.')
        for target in targets:
            if self.user and not self.system.user_can_write(target, self.user):
                self.log('%s is mounted but %s cannot write to it. Use "Give me write access" on the Drive page.' % (target, self.user.name))
        return targets

    def open_folder(self, target):
        return self.system.open_folder(target, self.user, self.log)

    def grant_write_access(self, target):
        if not self.user:
            raise OperationError('No desktop user detected; run the app through the launcher (pkexec or sudo).')
        self.log('Changing owner of %s to %s' % (target, self.user.name))
        _, err, rc = self.system.run_cmd(['chown', '%d:%d' % (self.user.uid, self.user.gid), target])
        if rc != 0:
            raise OperationError('chown failed: %s' % err)
        self.system.run_cmd(['chmod', 'u+rwx', target])

    def eject_and_lock(self, state):
        """Unmount everything, then power the USB device down. The drive relocks without power."""
        drive = state.drive
        drive.partitions = self.system.list_partitions(drive.disk)
        for part in drive.partitions:
            if part.mountpoint:
                self.log('Unmounting %s' % part.mountpoint)
                try:
                    self.system.unmount(part.node, self.log)
                except RuntimeError as exc:
                    raise OperationError('%s. Close any open files on the drive and try again.' % exc)
        try:
            how = self.system.power_off(drive, self.log)
        except (RuntimeError, OSError) as exc:
            raise OperationError('Unmounted, but could not power the drive off: %s. Unplug it to lock it.' % exc)
        self.log('Drive powered off via %s. It is locked again; unplug and reconnect it to use it.' % how)

    # --- password management ------------------------------------------------------

    def set_password(self, state, password, hint=''):
        drive = state.drive
        self._validate_password(password)
        status = self.status(drive)
        if status.security != protocol.STATUS_NOT_PROTECTED:
            raise OperationError('A password is already set (%s). Use Change password instead.' % status.security_name)
        length = protocol.password_blob_length(status)
        block = protocol.SecurityBlock(protocol.DEFAULT_ITERATIONS, protocol.DEFAULT_SALT, hint or '')
        self.log('Writing hashing parameters and hint to the drive')
        try:
            self._write_security_block(drive, block)
        except ScsiError as exc:
            raise OperationError('Could not write the security block: %s' % exc)
        blob = protocol.derive_password_blob(password, block, length)
        param = protocol.build_change_password_param(length, old_blob=None, new_blob=blob)
        self.log('Enabling password protection')
        try:
            self._exec(drive, protocol.cdb_change_password(len(param)), data_out=param)
        except ScsiError as exc:
            raise OperationError('The drive refused to set the password: %s' % exc)
        after = self.status(drive)
        if after.security != protocol.STATUS_UNLOCKED:
            raise OperationError('The drive reports %s after setting the password.' % after.security_name)
        # Community notes on these drives report the previous password can still
        # unlock some models. Re-applying the new password pushes the factory
        # default out of that slot. Harmless if the drive does not behave that way.
        param2 = protocol.build_change_password_param(length, old_blob=blob, new_blob=blob)
        try:
            self._exec(drive, protocol.cdb_change_password(len(param2)), data_out=param2)
        except ScsiError as exc:
            self.log('Second password application not accepted (%s); continuing.' % exc)
        state.block = block
        state.status = self.status(drive)
        self.log('Password set. The drive will ask for it after it is unplugged or powered off.')

    def change_password(self, state, old_password, new_password, hint=None):
        drive = state.drive
        self._validate_password(new_password)
        if not old_password:
            raise OperationError('Enter the current password.')
        status = self.status(drive)
        if status.security != protocol.STATUS_UNLOCKED:
            raise OperationError('The drive must be unlocked to change its password (currently: %s).' % status.security_name)
        length = protocol.password_blob_length(status)
        block = state.block or self._read_security_block(drive) or protocol.SecurityBlock()
        old_blob = protocol.derive_password_blob(old_password, block, length)
        new_blob = protocol.derive_password_blob(new_password, block, length)
        param = protocol.build_change_password_param(length, old_blob=old_blob, new_blob=new_blob)
        self.log('Changing password')
        try:
            self._exec(drive, protocol.cdb_change_password(len(param)), data_out=param)
        except ScsiError as exc:
            if protocol.is_wrong_password(exc.sense):
                raise OperationError('The current password is wrong.')
            raise OperationError('The drive refused the password change: %s' % exc)
        if hint is not None and hint != block.hint:
            new_block = protocol.SecurityBlock(block.iterations, block.salt, hint)
            try:
                self._write_security_block(drive, new_block)
                state.block = new_block
            except ScsiError as exc:
                self.log('Password changed but the hint could not be updated: %s' % exc)
        state.status = self.status(drive)
        self.log('Password changed.')

    def remove_password(self, state, old_password):
        drive = state.drive
        if not old_password:
            raise OperationError('Enter the current password.')
        status = self.status(drive)
        if status.security != protocol.STATUS_UNLOCKED:
            raise OperationError('The drive must be unlocked to remove its password (currently: %s).' % status.security_name)
        length = protocol.password_blob_length(status)
        block = state.block or self._read_security_block(drive) or protocol.SecurityBlock()
        old_blob = protocol.derive_password_blob(old_password, block, length)
        param = protocol.build_change_password_param(length, old_blob=old_blob, new_blob=None)
        self.log('Removing password protection')
        try:
            self._exec(drive, protocol.cdb_change_password(len(param)), data_out=param)
        except ScsiError as exc:
            if protocol.is_wrong_password(exc.sense):
                raise OperationError('The current password is wrong.')
            raise OperationError('The drive refused to remove the password: %s' % exc)
        after = self.status(drive)
        if after.security != protocol.STATUS_NOT_PROTECTED:
            raise OperationError('The drive reports %s after removing the password.' % after.security_name)
        cleared = protocol.SecurityBlock(block.iterations, block.salt, '')
        try:
            self._write_security_block(drive, cleared)
            state.block = cleared
        except ScsiError as exc:
            self.log('Password removed but the old hint could not be cleared: %s' % exc)
        state.status = after
        self.log('Password removed. The drive no longer asks for a password.')

    # --- erase ------------------------------------------------------------------

    def erase(self, state, fstype=None, label=''):
        """Reset the data encryption key. All data becomes unreadable instantly."""
        drive = state.drive
        drive.partitions = self.system.list_partitions(drive.disk)
        for part in drive.partitions:
            if part.mountpoint:
                self.log('Unmounting %s' % part.mountpoint)
                try:
                    self.system.unmount(part.node, self.log)
                except RuntimeError as exc:
                    raise OperationError('%s. Close any open files on the drive and try again.' % exc)
        status = self.status(drive)  # the key reset enabler is only valid right after this
        try:
            param = protocol.build_reset_key_param(status.cipher)
        except protocol.ProtocolError as exc:
            raise OperationError(str(exc))
        self.log('Resetting the data encryption key on %s (%s)' % (drive.control_node, status.cipher_name))
        try:
            self._exec(drive, protocol.cdb_reset_key(status.key_reset_enabler, len(param)), data_out=param)
        except ScsiError as exc:
            if status.cipher != protocol.FDE_CIPHER and exc.sense and (exc.sense.asc, exc.sense.ascq) == (0x26, 0x00):
                self.log('Drive rejected the combined key; retrying with a plain key')
                status = self.status(drive)
                param = protocol.build_reset_key_param(status.cipher, combine=0)
                try:
                    self._exec(drive, protocol.cdb_reset_key(status.key_reset_enabler, len(param)), data_out=param)
                except ScsiError as exc2:
                    raise OperationError('Key reset failed: %s' % exc2)
            else:
                raise OperationError('Key reset failed: %s' % exc)
        after = self.status(drive)
        self.log('Encryption key reset. Drive reports: %s.' % after.security_name)
        try:
            self._write_security_block(drive, protocol.SecurityBlock())
        except ScsiError:
            pass
        state.status = after
        state.block = None
        if fstype:
            time.sleep(1.0)
            new_disk = self.system.rescan_disk(drive.disk, self.log)
            try:
                node = self.system.format_partition_table(new_disk, fstype, label or drive.display_name, self.log)
            except RuntimeError as exc:
                raise OperationError('The key was reset but formatting failed: %s' % exc)
            self.log('Formatted %s as %s' % (node, fstype))
        return after

    def format_drive(self, state, fstype, label=''):
        """Repartition and format an accessible drive. Keeps the key and password; destroys the files."""
        drive = state.drive
        if fstype not in ('exfat', 'ntfs', 'ext4'):
            raise OperationError('Choose exFAT, NTFS or ext4.')
        status = self.status(drive)
        if not status.is_accessible:
            raise OperationError('Unlock the drive before formatting it (currently: %s).' % status.security_name)
        drive.partitions = self.system.list_partitions(drive.disk)
        for part in drive.partitions:
            if part.mountpoint:
                self.log('Unmounting %s' % part.mountpoint)
                try:
                    self.system.unmount(part.node, self.log)
                except RuntimeError as exc:
                    raise OperationError('%s. Close any open files on the drive and try again.' % exc)
        try:
            node = self.system.format_partition_table(drive.disk, fstype, label or drive.display_name, self.log)
        except RuntimeError as exc:
            raise OperationError('Formatting failed: %s' % exc)
        drive.partitions = self.system.list_partitions(drive.disk)
        self.log('Formatted %s as %s' % (node, fstype))
        return node

    # --- helpers ------------------------------------------------------------------

    @staticmethod
    def _validate_password(password):
        if not password:
            raise OperationError('The password cannot be empty.')
        if len(password) > 25:
            raise OperationError('WD Security limits passwords to 25 characters.')
