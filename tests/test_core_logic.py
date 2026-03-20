import importlib.util
import os
import sys
import types
import unittest
from unittest import mock


def _install_pyqt5_stubs():
    if 'PyQt5' in sys.modules:
        return

    pyqt5 = types.ModuleType('PyQt5')
    qtcore = types.ModuleType('PyQt5.QtCore')
    qtgui = types.ModuleType('PyQt5.QtGui')
    qtwidgets = types.ModuleType('PyQt5.QtWidgets')

    class _Qt:
        AlignCenter = 0
        AlignTop = 0
        Checked = 2

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

    qtcore.Qt = _Qt
    qtgui.QFontDatabase = _Dummy
    qtgui.QKeySequence = _Dummy

    qtwidgets.QApplication = _Dummy
    qtwidgets.QCheckBox = _Dummy
    qtwidgets.QFrame = _Dummy
    qtwidgets.QGridLayout = _Dummy
    qtwidgets.QHBoxLayout = _Dummy
    qtwidgets.QLabel = _Dummy
    qtwidgets.QLineEdit = _Dummy
    qtwidgets.QMessageBox = _Dummy
    qtwidgets.QPushButton = _Dummy
    qtwidgets.QShortcut = _Dummy
    qtwidgets.QTextEdit = _Dummy
    qtwidgets.QVBoxLayout = _Dummy

    sys.modules['PyQt5'] = pyqt5
    sys.modules['PyQt5.QtCore'] = qtcore
    sys.modules['PyQt5.QtGui'] = qtgui
    sys.modules['PyQt5.QtWidgets'] = qtwidgets


def _load_app_module():
    _install_pyqt5_stubs()
    root = os.path.dirname(os.path.dirname(__file__))
    app_path = os.path.join(root, 'app', 'wd-security.py')
    spec = importlib.util.spec_from_file_location('wd_security_app', app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FlagWidget:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, value):
        self.enabled = bool(value)


class DeviceDetectionTests(unittest.TestCase):
    def setUp(self):
        self.m = _load_app_module()

    def test_get_partname_detects_single_wd_disk_case_insensitive(self):
        disk_by_id = '/dev/disk/by-id'

        entries = ['usb-wd_My_Passport_1234-0:0', 'ata-Samsung_foo']
        full_link = f'{disk_by_id}/usb-wd_My_Passport_1234-0:0'

        orig_isdir = self.m.os.path.isdir

        def fake_isdir(path):
            if path == disk_by_id:
                return True
            return orig_isdir(path)

        with mock.patch.object(self.m.os.path, 'isdir', side_effect=fake_isdir), \
            mock.patch.object(self.m.os, 'listdir', return_value=entries), \
            mock.patch.object(self.m.os.path, 'islink', side_effect=lambda p: p == full_link), \
            mock.patch.object(self.m.os.path, 'realpath', return_value='/dev/sdb'):
            self.m.PARTNAME = ''
            window = self.m.WDSecurityWindow()
            count = window.get_partname()

        self.assertEqual(count, 1)
        self.assertEqual(self.m.PARTNAME, 'sdb')

    def test_multi_device_ambiguity_sets_warn_and_disables_actions(self):
        window = self.m.WDSecurityWindow()
        window.pw_box = _FlagWidget()
        window.decrypt_btn = _FlagWidget()
        window.mount_btn = _FlagWidget()
        seen_states = []
        log_lines = []

        window.set_state = lambda s: seen_states.append(s)
        window.append_log = lambda msg: log_lines.append(msg)
        window.get_partname = lambda: 2

        window.check_unlock_status()

        self.assertIn('WARN', seen_states)
        self.assertFalse(window.pw_box.enabled)
        self.assertFalse(window.decrypt_btn.enabled)
        self.assertFalse(window.mount_btn.enabled)
        self.assertTrue(any('Multiple WD block devices detected' in line for line in log_lines))


class SgMappingTests(unittest.TestCase):
    def setUp(self):
        self.m = _load_app_module()

    def test_find_sg_for_partname_prefers_sys_block_mapping(self):
        window = self.m.WDSecurityWindow()

        def fake_get_partname():
            self.m.PARTNAME = 'sda'
            return 1

        window.get_partname = fake_get_partname

        orig_isdir = self.m.os.path.isdir

        def fake_isdir(path):
            if path == '/sys/block/sda/device/scsi_generic':
                return True
            return orig_isdir(path)

        with mock.patch.object(self.m.os.path, 'isdir', side_effect=fake_isdir), \
            mock.patch.object(self.m.os, 'listdir', side_effect=lambda p: ['sg9'] if p == '/sys/block/sda/device/scsi_generic' else []):
            sg = window.find_sg_for_partname()

        self.assertEqual(sg, 'sg9')

    def test_find_sg_for_partname_falls_back_to_reverse_lookup(self):
        window = self.m.WDSecurityWindow()

        def fake_get_partname():
            self.m.PARTNAME = 'sdc'
            return 1

        window.get_partname = fake_get_partname

        orig_isdir = self.m.os.path.isdir

        def fake_isdir(path):
            if path in (
                '/sys/block/sdc/device/scsi_generic',
                '/sys/class/scsi_generic',
                '/sys/class/scsi_generic/sg3/device/block',
            ):
                return True
            return orig_isdir(path)

        def fake_listdir(path):
            if path == '/sys/block/sdc/device/scsi_generic':
                return []
            if path == '/sys/class/scsi_generic':
                return ['sg3']
            if path == '/sys/class/scsi_generic/sg3/device/block':
                return ['sdc']
            return []

        with mock.patch.object(self.m.os.path, 'isdir', side_effect=fake_isdir), \
            mock.patch.object(self.m.os, 'listdir', side_effect=fake_listdir):
            sg = window.find_sg_for_partname()

        self.assertEqual(sg, 'sg3')


class MountResolutionTests(unittest.TestCase):
    def setUp(self):
        self.m = _load_app_module()

    def test_resolve_mount_device_prefers_first_partition(self):
        window = self.m.WDSecurityWindow()

        with mock.patch.object(
            self.m,
            'run_cmd',
            return_value=('sda disk\nsda1 part\nsda2 part', '', 0),
        ):
            resolved = window.resolve_mount_device('sda')

        self.assertEqual(resolved, '/dev/sda1')

    def test_resolve_mount_device_falls_back_to_disk(self):
        window = self.m.WDSecurityWindow()

        with mock.patch.object(
            self.m,
            'run_cmd',
            return_value=('sdb disk', '', 0),
        ):
            resolved = window.resolve_mount_device('sdb')

        self.assertEqual(resolved, '/dev/sdb')


if __name__ == '__main__':
    unittest.main(verbosity=2)
