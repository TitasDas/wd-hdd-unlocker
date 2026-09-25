import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

from wdpassport import protocol  # noqa: E402
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
