import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

from wdpassport import protocol  # noqa: E402
from wdpassport import transport as transport_mod  # noqa: E402
from wdpassport.manager import DriveManager, OperationError  # noqa: E402
from wdpassport.simulator import SimulatedSystem, SimulatedTransport  # noqa: E402


def make(**kwargs):
    transport = SimulatedTransport(**kwargs)
    system = SimulatedSystem(transport)
    logs = []
    manager = DriveManager(transport=transport, system=system, log=logs.append)
    return manager, transport, system, logs


class ScanTests(unittest.TestCase):
    def test_scan_finds_control_node_and_hint(self):
        manager, transport, system, logs = make()
        states = manager.scan()
        self.assertEqual(len(states), 1)
        state = states[0]
        self.assertEqual(state.drive.control_node, '/dev/sg9')
        self.assertTrue(state.status.is_locked)
        self.assertEqual(state.hint, 'Demo drive hint')
        # first candidate /dev/sg8 failed, second answered
        self.assertTrue(any('control node /dev/sg9' in line for line in logs))

    def test_scan_with_no_drive(self):
        manager, transport, system, logs = make()
        system.powered_off = True
        self.assertEqual(manager.scan(), [])
        self.assertTrue(any('No WD USB device attached' in line for line in logs))


class UnlockTests(unittest.TestCase):
    def test_unlock_mounts_for_user(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        targets = manager.unlock(state, 'demo-pass')
        self.assertEqual(targets, ['/media/demo/My Passport'])
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)
        self.assertIn(('mount', '/dev/sdz1', '/media/demo/My Passport'), system.commands)
        unlock_cmds = [c for c in system.commands if c[0] == 'rescan']
        self.assertEqual(unlock_cmds, [('rescan', 'sdz')])

    def test_wrong_password_is_reported_clearly(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.unlock(state, 'nope')
        self.assertIn('Wrong password', str(ctx.exception))
        self.assertEqual(transport.security, protocol.STATUS_LOCKED)

    def test_blocked_after_too_many_attempts(self):
        manager, transport, system, logs = make(max_attempts=2)
        state = manager.scan()[0]
        for _ in range(2):
            with self.assertRaises(OperationError):
                manager.unlock(state, 'nope')
        self.assertEqual(transport.security, protocol.STATUS_LOCKED_BLOCKED)
        with self.assertRaises(OperationError) as ctx:
            manager.unlock(state, 'demo-pass')
        self.assertIn('Unplug', str(ctx.exception))

    def test_empty_password_rejected_before_touching_drive(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        before = len(transport.commands)
        with self.assertRaises(OperationError):
            manager.unlock(state, '')
        self.assertEqual(len(transport.commands), before)

    def test_already_unlocked_just_mounts(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]
        targets = manager.unlock(state, 'anything')
        self.assertEqual(len(targets), 1)
        self.assertFalse(any(c[1][:2] == b'\xc1\xe1' for c in transport.commands))

    def test_unlock_with_custom_salt_from_drive(self):
        transport = SimulatedTransport(security=protocol.STATUS_NOT_PROTECTED)
        block = protocol.SecurityBlock(iterations=1500, salt='ZQ', hint='custom')
        transport.handy[protocol.SECURITY_BLOCK] = protocol.build_security_block(block)
        transport.password_blob = protocol.derive_password_blob('pw', block)
        transport.security = protocol.STATUS_LOCKED
        system = SimulatedSystem(transport)
        manager = DriveManager(transport=transport, system=system)
        state = manager.scan()[0]
        self.assertEqual(state.hint, 'custom')
        manager.unlock(state, 'pw')
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)

    def test_mount_warns_when_user_cannot_write(self):
        manager, transport, system, logs = make()
        system.writable = False
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        self.assertTrue(any('cannot write' in line for line in logs))

    def test_already_mounted_partition_is_reused(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        system.mounts['/dev/sdz1'] = '/media/demo/existing'
        state = manager.scan()[0]
        self.assertEqual(manager.mount(state), ['/media/demo/existing'])
        self.assertFalse(any(c[0] == 'mount' for c in system.commands))


class MountRaceTests(unittest.TestCase):
    def test_mount_uses_desktop_mount_when_own_mount_loses_race(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)

        def racy_mount(part, user, log):
            system.mounts[part.node] = '/media/demo/by-desktop'
            raise RuntimeError('mount failed for %s: already mounted' % part.node)

        system.mount_partition = racy_mount
        state = manager.scan()[0]
        self.assertEqual(manager.mount(state), ['/media/demo/by-desktop'])
        self.assertTrue(any('mounted by the desktop' in line for line in logs))


class LockTests(unittest.TestCase):
    def test_eject_unmounts_then_powers_off_and_relocks(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        manager.eject_and_lock(state)
        self.assertIn(('unmount', '/dev/sdz1'), system.commands)
        self.assertIn(('power-off', '/dev/sdz'), system.commands)
        self.assertEqual(transport.security, protocol.STATUS_LOCKED)
        self.assertEqual(manager.scan(), [])


class PasswordTests(unittest.TestCase):
    def test_set_password_on_unprotected_drive(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]
        manager.set_password(state, 'new-secret', hint='pet name')
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)
        self.assertEqual(state.hint, 'pet name')
        stored = protocol.parse_security_block(transport.handy[protocol.SECURITY_BLOCK])
        self.assertEqual(stored.salt, 'WDC.')
        self.assertEqual(stored.iterations, 1000)
        self.assertEqual(transport.password_blob, protocol.derive_password_blob('new-secret'))
        # Lock and unlock again with the new password
        system.power_off(state.drive, logs.append)
        system.powered_off = False
        state = manager.scan()[0]
        self.assertTrue(state.status.is_locked)
        manager.unlock(state, 'new-secret')
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)

    def test_set_password_refused_when_already_protected(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.set_password(state, 'x')
        self.assertIn('already set', str(ctx.exception))

    def test_password_length_limit(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]
        with self.assertRaises(OperationError):
            manager.set_password(state, 'x' * 26)

    def test_change_password_and_hint(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        manager.change_password(state, 'demo-pass', 'second', hint='new hint')
        self.assertEqual(transport.password_blob, protocol.derive_password_blob('second'))
        self.assertEqual(protocol.parse_security_block(transport.handy[protocol.SECURITY_BLOCK]).hint, 'new hint')
        with self.assertRaises(OperationError) as ctx:
            manager.change_password(state, 'demo-pass', 'third')
        self.assertIn('current password is wrong', str(ctx.exception))

    def test_change_requires_unlocked(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.change_password(state, 'demo-pass', 'second')
        self.assertIn('must be unlocked', str(ctx.exception))

    def test_remove_password_clears_hint(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        manager.remove_password(state, 'demo-pass')
        self.assertEqual(transport.security, protocol.STATUS_NOT_PROTECTED)
        self.assertIsNone(transport.password_blob)
        self.assertEqual(state.hint, '')
        system.power_off(state.drive, logs.append)
        system.powered_off = False
        state = manager.scan()[0]
        self.assertEqual(state.status.security, protocol.STATUS_NOT_PROTECTED)


class FormatTests(unittest.TestCase):
    def test_format_requires_accessible_drive(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.format_drive(state, 'exfat', 'X')
        self.assertIn('Unlock the drive', str(ctx.exception))
        self.assertIsNone(system.formatted)

    def test_format_unmounts_then_formats_and_keeps_password(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        node = manager.format_drive(state, 'ntfs', 'Work')
        self.assertEqual(node, '/dev/sdz1')
        self.assertIn(('unmount', '/dev/sdz1'), system.commands)
        self.assertEqual(system.formatted, ('sdz', 'ntfs', 'Work'))
        self.assertEqual(transport.key_resets, 0)
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)
        self.assertEqual(state.drive.partitions[0].fstype, 'ntfs')
        self.assertEqual(state.drive.partitions[0].label, 'Work')

    def test_format_rejects_unknown_filesystem(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]
        with self.assertRaises(OperationError):
            manager.format_drive(state, 'btrfs', 'X')

    def test_format_reports_tool_failure(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]

        def broken(disk, fstype, label, log):
            raise RuntimeError('mkfs.exfat is not installed')

        system.format_partition_table = broken
        with self.assertRaises(OperationError) as ctx:
            manager.format_drive(state, 'exfat', 'X')
        self.assertIn('mkfs.exfat', str(ctx.exception))

    def test_format_stops_when_unmount_fails(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        system.mounts['/dev/sdz1'] = '/media/demo/busy'

        def busy(node, log):
            raise RuntimeError('could not unmount /dev/sdz1: target is busy')

        system.unmount = busy
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.format_drive(state, 'exfat', 'X')
        self.assertIn('Close any open files', str(ctx.exception))
        self.assertIsNone(system.formatted)


class MoreManagerTests(unittest.TestCase):
    def test_unsupported_drive_has_no_status(self):
        transport = SimulatedTransport(node='/dev/sg42')
        system = SimulatedSystem(transport)
        system.candidates = ['/dev/sg8', '/dev/sdz']  # nothing here answers
        logs = []
        manager = DriveManager(transport=transport, system=system, log=logs.append)
        state = manager.scan()[0]
        self.assertFalse(state.supported)
        self.assertEqual(state.drive.control_node, '')
        self.assertTrue(any('did not answer' in line for line in logs))
        with self.assertRaises(OperationError):
            manager.unlock(state, 'demo-pass')

    def test_refresh_keeps_control_node_first(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        before = len(transport.commands)
        state = manager.refresh(state)
        self.assertEqual(state.drive.sg_candidates[0], '/dev/sg9')
        # only status + handy store on the known node, no probing of /dev/sg8
        self.assertEqual([c[0] for c in transport.commands[before:]], ['/dev/sg9', '/dev/sg9'])

    def test_grant_write_access_requires_desktop_user(self):
        transport = SimulatedTransport()
        system = SimulatedSystem(transport, user=False)
        manager = DriveManager(transport=transport, system=system)
        with self.assertRaises(OperationError):
            manager.grant_write_access('/mnt/x')
        manager2, transport2, system2, logs2 = make()
        manager2.grant_write_access('/media/demo/x')
        self.assertIn(('chown', '1000:1000', '/media/demo/x'), system2.commands)

    def test_eject_reports_busy_mount(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        system.mounts['/dev/sdz1'] = '/media/demo/busy'

        def busy(node, log):
            raise RuntimeError('could not unmount /dev/sdz1: target is busy')

        system.unmount = busy
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.eject_and_lock(state)
        self.assertIn('Close any open files', str(ctx.exception))
        self.assertFalse(system.powered_off)

    def test_eject_reports_power_off_failure(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)

        def no_power(drive, log):
            raise RuntimeError('no way to power off')

        system.power_off = no_power
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.eject_and_lock(state)
        self.assertIn('Unplug it to lock it', str(ctx.exception))

    def test_mount_without_partitions_explains(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        system.parts = []
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.mount(state)
        self.assertIn('no partitions', str(ctx.exception))

    def test_mount_skips_unformatted_partition(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        system.parts[0].fstype = ''
        state = manager.scan()[0]
        with self.assertRaises(OperationError) as ctx:
            manager.mount(state)
        self.assertIn('nothing could be mounted', str(ctx.exception))
        self.assertTrue(any('no recognisable filesystem' in line for line in logs))

    def test_mount_after_reenumeration_updates_disk(self):
        manager, transport, system, logs = make(security=protocol.STATUS_NOT_PROTECTED)
        state = manager.scan()[0]
        system.rescan_disk = lambda disk, log, wait_s=0: 'sdy'
        original_describe = system.describe_drive
        system.describe_drive = lambda disk: original_describe(disk)
        system.parts = [type(system.parts[0])('sdy1', 'exfat', 'Moved', 10)]
        targets = manager.mount(state)
        self.assertEqual(state.drive.disk, 'sdy')
        self.assertEqual(targets, ['/media/demo/Moved'])
        self.assertTrue(any('re-enumerated' in line for line in logs))

    def test_change_password_hint_write_failure_is_logged_not_fatal(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        original = transport.execute

        def flaky(node, cdb, data_out=None, data_in_len=0):
            if bytes(cdb)[0] == 0xDA:
                raise transport_mod.ScsiError('write refused', node=node)
            return original(node, cdb, data_out=data_out, data_in_len=data_in_len)

        transport.execute = flaky
        manager.change_password(state, 'demo-pass', 'next', hint='new')
        self.assertEqual(transport.password_blob, protocol.derive_password_blob('next'))
        self.assertTrue(any('hint could not be updated' in line for line in logs))

    def test_erase_retries_with_plain_key_when_combined_rejected(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        original = transport.execute
        seen = []

        def picky(node, cdb, data_out=None, data_in_len=0):
            if bytes(cdb)[:2] == b'\xc1\xe3':
                seen.append(data_out[3])
                if data_out[3] == 1:
                    raise transport_mod.ScsiError('bad', sense=protocol.SenseInfo(0x5, 0x26, 0x00), node=node)
            return original(node, cdb, data_out=data_out, data_in_len=data_in_len)

        transport.execute = picky
        manager.erase(state)
        self.assertEqual(seen, [1, 0])
        self.assertEqual(transport.key_resets, 1)

    def test_erase_other_failure_is_reported(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]

        def refuse(node, cdb, data_out=None, data_in_len=0):
            if bytes(cdb)[:2] == b'\xc1\xe3':
                raise transport_mod.ScsiError('nope', sense=protocol.SenseInfo(0x5, 0x24, 0x00), node=node)
            return SimulatedTransport.execute(transport, node, cdb, data_out=data_out, data_in_len=data_in_len)

        transport.execute = refuse
        with self.assertRaises(OperationError) as ctx:
            manager.erase(state)
        self.assertIn('Key reset failed', str(ctx.exception))

    def test_damaged_security_block_falls_back_to_defaults(self):
        manager, transport, system, logs = make()
        raw = bytearray(transport.handy[protocol.SECURITY_BLOCK])
        raw[100] ^= 0xFF
        transport.handy[protocol.SECURITY_BLOCK] = bytes(raw)
        state = manager.scan()[0]
        self.assertIsNone(state.block)
        self.assertTrue(any('damaged' in line for line in logs))
        # default parameters still unlock a drive whose password used the defaults
        manager.unlock(state, 'demo-pass')
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)

    def test_unlock_status_mismatch_is_reported(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        original = transport.execute

        def sticky(node, cdb, data_out=None, data_in_len=0):
            result = original(node, cdb, data_out=data_out, data_in_len=data_in_len)
            if bytes(cdb)[:2] == b'\xc1\xe1':
                transport.security = protocol.STATUS_LOCKED
            return result

        transport.execute = sticky
        with self.assertRaises(OperationError) as ctx:
            manager.unlock(state, 'demo-pass')
        self.assertIn('still reports', str(ctx.exception))


class EraseTests(unittest.TestCase):
    def test_erase_uses_fresh_enabler_and_formats(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.unlock(state, 'demo-pass')
        after = manager.erase(state, fstype='exfat', label='Fresh')
        self.assertEqual(transport.key_resets, 1)
        self.assertEqual(after.security, protocol.STATUS_NOT_PROTECTED)
        self.assertIn(('unmount', '/dev/sdz1'), system.commands)
        self.assertEqual(system.formatted, ('sdz', 'exfat', 'Fresh'))

    def test_erase_works_on_locked_drive(self):
        manager, transport, system, logs = make()
        state = manager.scan()[0]
        manager.erase(state)
        self.assertEqual(transport.security, protocol.STATUS_NOT_PROTECTED)
        self.assertIsNone(transport.password_blob)

    def test_fde_drive_erase_sends_empty_key(self):
        manager, transport, system, logs = make(cipher=0x30)
        state = manager.scan()[0]
        manager.erase(state)
        reset = [c for c in transport.commands if c[1][:2] == b'\xc1\xe3'][0]
        self.assertEqual(len(reset[2]), 8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
