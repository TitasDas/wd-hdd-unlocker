"""An in-memory WD drive for tests and the --demo UI mode.

`SimulatedTransport` implements the vendor commands against a small state
machine that mirrors the documented drive behaviour. `SimulatedSystem` stands
in for the `devices` module so the whole manager can run without hardware.
"""

import os
import struct

from . import protocol
from .devices import Drive, Partition, DesktopUser
from .transport import ScsiError


class SimulatedTransport:
    name = 'simulated'

    def __init__(self, security=protocol.STATUS_LOCKED, cipher=0x28, password='demo-pass', hint='Demo drive hint',
                 node='/dev/sg9', max_attempts=5):
        self.node = node
        self.security = security
        self.cipher = cipher
        self.password_length = 16 if cipher in protocol.AES128_CIPHERS else 32
        self.block = protocol.SecurityBlock(hint=hint) if security != protocol.STATUS_NOT_PROTECTED else None
        self.password_blob = (protocol.derive_password_blob(password, self.block or protocol.SecurityBlock(), self.password_length)
                              if security != protocol.STATUS_NOT_PROTECTED else None)
        self.handy = {}
        if self.block:
            self.handy[protocol.SECURITY_BLOCK] = protocol.build_security_block(self.block)
        self.failed_attempts = 0
        self.max_attempts = max_attempts
        self.key_reset_enabler = os.urandom(4)
        self.enabler_valid = False
        self.commands = []
        self.key_resets = 0

    # -- helpers --
    def _sense(self, key, asc, ascq):
        raise ScsiError(protocol.describe_sense(protocol.SenseInfo(key, asc, ascq)),
                        sense=protocol.SenseInfo(key, asc, ascq), node=self.node)

    def _default_blob(self):
        return bytes(self.password_length)

    def execute(self, node, cdb, data_out=None, data_in_len=0):
        cdb = bytes(cdb)
        self.commands.append((node, cdb, bytes(data_out) if data_out is not None else None, data_in_len))
        if node != self.node:
            self._sense(0x5, 0x20, 0x00)
        op = cdb[0]
        sub = cdb[1]
        enabler_was_valid = self.enabler_valid
        self.enabler_valid = False

        if op == 0xC0 and sub == 0x45:
            self.key_reset_enabler = os.urandom(4)
            self.enabler_valid = True
            data = bytearray(48)
            data[0] = 0x45
            data[3] = self.security
            data[4] = self.cipher
            data[6:8] = struct.pack('>H', self.password_length)
            data[8:12] = self.key_reset_enabler
            data[15] = 2
            data[16] = 0x28
            data[17] = 0x30
            return bytes(data[:data_in_len])

        if op == 0xD8:
            block = struct.unpack('>I', cdb[2:6])[0]
            return self.handy.get(block, bytes(512))

        if op == 0xDA:
            if self.security not in (protocol.STATUS_NOT_PROTECTED, protocol.STATUS_UNLOCKED):
                self._sense(0x7, 0x74, 0x71)
            block = struct.unpack('>I', cdb[2:6])[0]
            self.handy[block] = bytes(data_out)
            return b''

        if op == 0xC1 and sub == 0xE1:
            expected = 8 + self.password_length
            if len(data_out) != expected or struct.unpack('>H', cdb[7:9])[0] != expected:
                self._sense(0x5, 0x24, 0x00)
            if self.security == protocol.STATUS_LOCKED_BLOCKED:
                self._sense(0x5, 0x74, 0x80)
            if self.security != protocol.STATUS_LOCKED:
                self._sense(0x5, 0x74, 0x81)
            blob = data_out[8:]
            if blob != self.password_blob:
                self.failed_attempts += 1
                if self.failed_attempts >= self.max_attempts:
                    self.security = protocol.STATUS_LOCKED_BLOCKED
                self._sense(0x5, 0x74, 0x40)
            self.security = protocol.STATUS_UNLOCKED
            self.failed_attempts = 0
            return b''

        if op == 0xC1 and sub == 0xE2:
            length = self.password_length
            expected = 8 + 2 * length
            if len(data_out) != expected:
                self._sense(0x5, 0x24, 0x00)
            flags = data_out[3]
            old_blob = data_out[8:8 + length]
            new_blob = data_out[8 + length:8 + 2 * length]
            old_default = bool(flags & 0x01)
            new_default = bool(flags & 0x10)
            if old_default and new_default:
                self._sense(0x5, 0x26, 0x00)
            if old_default:
                if self.security != protocol.STATUS_NOT_PROTECTED:
                    self._sense(0x5, 0x74, 0x81)
                self.password_blob = new_blob
                self.security = protocol.STATUS_UNLOCKED
                return b''
            if self.security != protocol.STATUS_UNLOCKED:
                self._sense(0x5, 0x74, 0x81)
            if old_blob != self.password_blob:
                self.failed_attempts += 1
                self._sense(0x5, 0x74, 0x40)
            if new_default:
                self.password_blob = None
                self.security = protocol.STATUS_NOT_PROTECTED
            else:
                self.password_blob = new_blob
            return b''

        if op == 0xC1 and sub == 0xE3:
            if not enabler_was_valid or cdb[2:6] != self.key_reset_enabler:
                self._sense(0x5, 0x24, 0x00)
            cipher = data_out[4]
            key_bits = struct.unpack('>H', data_out[6:8])[0]
            if cipher == protocol.FDE_CIPHER and key_bits != 0:
                self._sense(0x5, 0x26, 0x00)
            self.key_resets += 1
            self.cipher = cipher
            self.security = protocol.STATUS_NOT_PROTECTED
            self.password_blob = None
            self.failed_attempts = 0
            return b''

        self._sense(0x5, 0x20, 0x00)


class SimulatedSystem:
    """Stand-in for the devices module with a fake disk and mount table."""

    def __init__(self, transport, disk='sdz', model='My_Passport_25E1', user=True, locked_has_parts=False):
        self.transport = transport
        self.disk = disk
        self.model = model
        self.locked_has_parts = locked_has_parts
        self.user_obj = DesktopUser('demo', 1000, 1000, '/home/demo') if user else None
        self.mounts = {}
        self.commands = []
        self.powered_off = False
        self.formatted = None
        self.writable = True
        self.opened = []
        self.parts = [Partition(disk + '1', 'ntfs', 'My Passport', 2 * 10 ** 12)]
        self.candidates = None

    # discovery
    def wd_usb_present(self):
        return [] if self.powered_off else ['Bus 002 Device 004: ID 1058:25e1 Western Digital Technologies, Inc.']

    def find_wd_disks(self):
        return [] if self.powered_off else [self.disk]

    def describe_drive(self, disk):
        drive = Drive(disk)
        drive.model = self.model
        drive.vendor = 'WD'
        drive.serial = 'WX12345678'
        drive.usb_id = '1058:25e1'
        drive.size = 2 * 10 ** 12
        drive.partitions = self.list_partitions(disk)
        drive.sg_candidates = list(self.candidates) if self.candidates else ['/dev/sg8', self.transport.node, '/dev/' + disk]
        return drive

    def list_partitions(self, disk):
        if self.powered_off:
            return []
        if self.transport.security in (protocol.STATUS_LOCKED, protocol.STATUS_LOCKED_BLOCKED) and not self.locked_has_parts:
            return []
        out = []
        for p in self.parts:
            out.append(Partition(p.name, p.fstype, p.label, p.size, self.mounts.get(p.node, ''), p.uuid))
        return out

    def desktop_user(self):
        return self.user_obj

    # mounting
    def rescan_disk(self, disk, log, wait_s=0):
        self.commands.append(('rescan', disk))
        return disk

    def wait_for_automount(self, disk, wait_s=0):
        return self.list_partitions(disk)

    def mount_partition(self, part, user, log):
        target = '/media/%s/%s' % (user.name if user else 'root', part.label or part.name)
        self.mounts[part.node] = target
        self.commands.append(('mount', part.node, target))
        return target

    def mount_target(self, node):
        return self.mounts.get(node, '')

    def unmount(self, node, log):
        self.commands.append(('unmount', node))
        self.mounts.pop(node, None)
        return True

    def user_can_write(self, target, user):
        return self.writable

    def open_folder(self, target, user, log):
        self.opened.append(target)
        return True

    def power_off(self, drive, log):
        self.commands.append(('power-off', drive.node))
        self.powered_off = True
        self.transport.security = protocol.STATUS_LOCKED if self.transport.password_blob else protocol.STATUS_NOT_PROTECTED
        return 'simulated'

    def run_cmd(self, args, **kwargs):
        self.commands.append(tuple(args))
        return '', '', 0

    def format_partition_table(self, disk, fstype, label, log):
        self.formatted = (disk, fstype, label)
        self.parts = [Partition(disk + '1', fstype, label, 2 * 10 ** 12)]
        return '/dev/' + disk + '1'
