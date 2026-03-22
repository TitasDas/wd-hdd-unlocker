import os
import tempfile
import unittest
from unittest import mock

from tests.test_core_logic import _load_app_module


class _FlagWidget:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, value):
        self.enabled = bool(value)


class _TextBox(_FlagWidget):
    def __init__(self, value=''):
        super().__init__()
        self._value = value

    def text(self):
        return self._value

    def clear(self):
        self._value = ''


class UserFlowSimulationTests(unittest.TestCase):
    def setUp(self):
        self.m = _load_app_module()

    def _build_window_minimal(self):
        w = self.m.WDSecurityWindow()
        w.pw_box = _TextBox('testpass')
        w.decrypt_btn = _FlagWidget()
        w.mount_btn = _FlagWidget()
        w.message_box = mock.Mock()
        return w

    def test_no_drive_flow_sets_waiting_and_disables_password(self):
        w = self._build_window_minimal()
        states = []
        logs = []
        w.set_state = lambda s: states.append(s)
        w.append_log = lambda msg: logs.append(msg)

        with mock.patch.object(self.m, 'run_cmd', return_value=('', '', 0)):
            w.check_wd_drive()

        self.assertIn('WAITING', states)
        self.assertFalse(w.pw_box.enabled)
        self.assertTrue(any('No Western Digital drive attached.' in x for x in logs))

    def test_unlock_flow_simulated_success(self):
        w = self._build_window_minimal()
        states = []
        logs = []
        mount_called = {'v': False}

        w.set_state = lambda s: states.append(s)
        w.append_log = lambda msg: logs.append(msg)
        w.mount_wd = lambda: mount_called.__setitem__('v', True)
        w.find_type13_sg_for_partname = lambda: ['sg0']
        w.find_sg_for_partname = lambda: 'sg0'

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            payload = tf.name

        def fake_run_cmd(args, check=False):
            if args[:1] == ['sg_raw']:
                return ('', '', 0)
            return ('', '', 0)

        with mock.patch.object(self.m, 'run_cmd', side_effect=fake_run_cmd):
            w.unlock_drive(payload)

        self.assertTrue(mount_called['v'])
        self.assertIn('MOUNT', states)
        self.assertTrue(any('The WD drive is now unlocked' in x for x in logs))
        self.assertFalse(os.path.exists(payload))

    def test_unlock_flow_simulated_illegal_request(self):
        w = self._build_window_minimal()
        errors = []
        logs = []

        w.append_log = lambda msg: logs.append(msg)
        w.find_type13_sg_for_partname = lambda: ['sg0']
        w.find_sg_for_partname = lambda: 'sg0'
        w.show_error = lambda title, msg: errors.append((title, msg))

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            payload = tf.name

        def fake_run_cmd(args, check=False):
            if args[:1] == ['sg_raw']:
                err = 'SCSI Status: Check Condition Sense key: Illegal Request ASC=74, ASCQ=81 (hex)'
                return ('', err, 2)
            return ('', '', 0)

        with mock.patch.object(self.m, 'run_cmd', side_effect=fake_run_cmd):
            w.unlock_drive(payload)

        self.assertTrue(errors)
        self.assertEqual(errors[0][0], 'Unlock Failed')
        self.assertIn('Illegal Request', errors[0][1])
        self.assertTrue(any('Unlock attempt failed on /dev/sg0' in x for x in logs))
        self.assertFalse(os.path.exists(payload))

    def test_mount_flow_recovers_from_invalid_existing_target(self):
        w = self._build_window_minimal()
        states = []
        logs = []

        w.set_state = lambda s: states.append(s)
        w.append_log = lambda msg: logs.append(msg)
        w.get_partname = lambda: setattr(self.m, 'PARTNAME', 'sda') or 1
        w.resolve_mount_device = lambda p: '/dev/sda1'

        calls = []

        def fake_run_cmd(args, check=False):
            calls.append(tuple(args))
            if args[:3] == ['findmnt', '-n', '-o']:
                return ('/media/root/wd-volume', '', 0)
            if args[:1] == ['umount']:
                return ('', '', 0)
            if args[:1] == ['mount']:
                return ('', '', 0)
            return ('', '', 0)

        with mock.patch.object(self.m, 'run_cmd', side_effect=fake_run_cmd), \
            mock.patch.object(self.m.os.path, 'isdir', side_effect=lambda p: p.startswith('/mnt/wd-security-')), \
            mock.patch.object(self.m.os.path, 'exists', return_value=False):
            w.mount_wd()

        self.assertIn('DONE', states)
        self.assertTrue(any(c[0] == 'umount' for c in calls))
        self.assertTrue(any('Re-mounting to a safe path' in x for x in logs))

    def test_mount_flow_reports_accessible_path_when_mount_commands_error(self):
        w = self._build_window_minimal()
        states = []
        logs = []
        opened = []

        w.set_state = lambda s: states.append(s)
        w.append_log = lambda msg: logs.append(msg)
        w.try_open_mount_path = lambda p: opened.append(p) or True
        w.get_partname = lambda: setattr(self.m, 'PARTNAME', 'sda') or 1
        w.resolve_mount_device = lambda p: '/dev/sda1'

        def fake_run_cmd(args, check=False):
            if args[:1] == ['partprobe']:
                return ('', '', 0)
            if args[:3] == ['findmnt', '-n', '-o']:
                return ('', '', 1)
            if args[:1] == ['mkdir']:
                return ('', '', 0)
            if args[:1] == ['mount']:
                return ('', 'permission denied', 1)
            if args[:2] == ['udisksctl', 'mount']:
                return ('', 'not authorized', 1)
            return ('', '', 0)

        with mock.patch.object(self.m, 'run_cmd', side_effect=fake_run_cmd), \
            mock.patch.object(self.m.os.path, 'exists', return_value=False), \
            mock.patch.object(w, 'find_existing_mount_target', return_value='/home/mnt/wd-drive'):
            w.mount_wd()

        self.assertIn('WARN', states)
        self.assertTrue(any('already accessible' in x for x in logs))
        self.assertTrue(any('/home/mnt/wd-drive' in x for x in logs))
        self.assertEqual(opened, ['/home/mnt/wd-drive'])
        self.assertFalse(any('Mount manually if needed' in x for x in logs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
