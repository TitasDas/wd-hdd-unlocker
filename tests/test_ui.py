"""Headless tests of the Qt interface against the simulated drive."""

import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
    HAVE_QT = True
except ImportError:  # pragma: no cover - exercised on machines without PyQt5
    HAVE_QT = False

from wdpassport import protocol  # noqa: E402
from wdpassport.manager import DriveManager  # noqa: E402
from wdpassport.simulator import SimulatedSystem, SimulatedTransport  # noqa: E402

if HAVE_QT:
    from wdpassport.ui import dialogs, theme  # noqa: E402
    from wdpassport.ui.main_window import MainWindow  # noqa: E402

_app = None


def app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def settle(window, timeout=10.0):
    """Pump the event loop until the background worker is idle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app().processEvents()
        if not window.busy:
            app().processEvents()
            return
        time.sleep(0.01)
    raise AssertionError('window still busy after %.0fs' % timeout)


def make_window(**kwargs):
    transport = SimulatedTransport(**kwargs)
    system = SimulatedSystem(transport)
    manager = DriveManager(transport=transport, system=system)
    window = MainWindow(manager, demo=True)
    settle(window)
    return window, transport, system


@unittest.skipUnless(HAVE_QT, 'PyQt5 not installed')
class MainWindowTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_locked_drive_renders_and_gates_actions(self):
        window, transport, system = make_window()
        self.assertEqual(window.top_pill.text(), 'LOCKED')
        self.assertIn('Demo drive hint', window.unlock_hint.text())
        self.assertTrue(window.act_unlock.isVisible() or window.act_unlock.isEnabled())
        self.assertFalse(window.unlock_btn.isEnabled())
        window.unlock_pw.edit.setText('x')
        self.assertTrue(window.unlock_btn.isEnabled())
        self.assertFalse(window.change_btn.isEnabled())
        self.assertFalse(window.format_btn.isEnabled())
        self.assertTrue(window.erase_btn.isEnabled())
        window.close()

    def test_unlock_mounts_and_opens_folder(self):
        window, transport, system = make_window()
        window.unlock_pw.edit.setText('demo-pass')
        window.do_unlock()
        settle(window)
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)
        self.assertEqual(window.top_pill.text(), 'UNLOCKED')
        self.assertEqual(window.table.rowCount(), 1)
        self.assertEqual(window.table.item(0, 4).text(), '/media/demo/My Passport')
        self.assertEqual(system.opened, ['/media/demo/My Passport'])
        self.assertEqual(window.unlock_pw.text(), '')
        self.assertTrue(window.act_open.isEnabled())
        self.assertTrue(window.change_btn.isEnabled())
        self.assertTrue(window.format_btn.isEnabled())
        window.close()

    def test_wrong_password_shows_error_and_recovers(self):
        window, transport, system = make_window()
        window.unlock_pw.edit.setText('wrong')
        with mock.patch.object(QMessageBox, 'warning', return_value=None) as warn:
            window.do_unlock()
            settle(window)
        self.assertTrue(warn.called)
        self.assertIn('Wrong password', warn.call_args[0][2])
        self.assertEqual(window.top_pill.text(), 'LOCKED')
        self.assertFalse(window.busy)
        window.close()

    def test_eject_powers_off_and_clears_drive(self):
        window, transport, system = make_window(security=protocol.STATUS_NOT_PROTECTED)
        with mock.patch.object(dialogs, 'confirm', return_value=True), \
                mock.patch('wdpassport.ui.main_window.confirm', return_value=True):
            window.do_eject()
            settle(window)
        self.assertTrue(system.powered_off)
        self.assertEqual(window.top_pill.text(), 'NO DRIVE')
        self.assertTrue(window.empty_card.isVisibleTo(window))
        window.close()

    def test_set_password_flow_through_dialog(self):
        window, transport, system = make_window(security=protocol.STATUS_NOT_PROTECTED)
        self.assertTrue(window.set_btn.isEnabled())
        with mock.patch.object(dialogs.SetPasswordDialog, 'exec_', return_value=QDialog.Accepted), \
                mock.patch.object(dialogs.SetPasswordDialog, 'values', return_value=('s3cret', 'a hint')), \
                mock.patch.object(QMessageBox, 'information', return_value=None):
            window.do_set_password()
            settle(window)
        self.assertEqual(transport.security, protocol.STATUS_UNLOCKED)
        self.assertEqual(window.kv.values['Password hint'].text(), 'a hint')
        self.assertEqual(window.top_pill.text(), 'UNLOCKED')
        window.close()

    def test_format_flow_through_dialog(self):
        window, transport, system = make_window(security=protocol.STATUS_NOT_PROTECTED)
        with mock.patch.object(dialogs.FormatDialog, 'exec_', return_value=QDialog.Accepted), \
                mock.patch.object(dialogs.FormatDialog, 'values', return_value=('ext4', 'Backups')), \
                mock.patch('wdpassport.ui.main_window.confirm', return_value=True), \
                mock.patch.object(QMessageBox, 'information', return_value=None):
            window.do_format()
            settle(window)
        self.assertEqual(system.formatted, ('sdz', 'ext4', 'Backups'))
        self.assertEqual(window.table.item(0, 1).text(), 'ext4')
        self.assertEqual(window.table.item(0, 2).text(), 'Backups')
        window.close()

    def test_erase_flow_through_dialog(self):
        window, transport, system = make_window()
        with mock.patch.object(dialogs.EraseDialog, 'exec_', return_value=QDialog.Accepted), \
                mock.patch.object(dialogs.EraseDialog, 'values', return_value=('exfat', 'Clean')), \
                mock.patch('wdpassport.ui.main_window.confirm', return_value=True), \
                mock.patch.object(QMessageBox, 'information', return_value=None):
            window.do_erase()
            settle(window)
        self.assertEqual(transport.key_resets, 1)
        self.assertEqual(system.formatted, ('sdz', 'exfat', 'Clean'))
        self.assertEqual(window.top_pill.text(), 'NO PASSWORD SET')
        window.close()

    def test_theme_toggle_and_pages(self):
        window, transport, system = make_window()
        self.assertEqual(window.theme_name, 'light')
        window.toggle_theme()
        self.assertEqual(window.theme_name, 'dark')
        self.assertIn(theme.DARK['sidebar'], window.styleSheet())
        for key in ('drive', 'unlock', 'security', 'advanced', 'activity'):
            window.show_page(key)
            self.assertIs(window.stack.currentWidget(), window.pages[key])
            self.assertTrue(window.nav_buttons[key].isChecked())
        window.close()

    def test_diagnostics_mask_serial(self):
        window, transport, system = make_window()
        text = window.diagnostics_text()
        self.assertIn('WX1…5678', text)
        self.assertNotIn('WX12345678', text)
        self.assertIn('Control node: /dev/sg9', text)
        window.close()

    def test_no_drive_state(self):
        transport = SimulatedTransport()
        system = SimulatedSystem(transport)
        system.powered_off = True
        window = MainWindow(DriveManager(transport=transport, system=system), demo=True)
        settle(window)
        self.assertEqual(window.top_pill.text(), 'NO DRIVE')
        self.assertFalse(window.unlock_pw.isEnabled())
        self.assertEqual(window.drive_combo.count(), 0)
        window.close()

    def test_unsupported_drive_state(self):
        transport = SimulatedTransport(node='/dev/sg42')
        system = SimulatedSystem(transport)
        system.candidates = ['/dev/sg8', '/dev/sdz']  # nothing here answers
        window = MainWindow(DriveManager(transport=transport, system=system), demo=True)
        settle(window)
        self.assertEqual(window.top_pill.text(), 'UNSUPPORTED')
        self.assertTrue(window.unsupported_card.isVisibleTo(window))
        self.assertFalse(window.erase_btn.isEnabled())
        window.close()


@unittest.skipUnless(HAVE_QT, 'PyQt5 not installed')
class DialogTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_set_password_dialog_validation(self):
        dlg = dialogs.SetPasswordDialog('Demo')
        self.assertFalse(dlg.ok.isEnabled())
        dlg.new.edit.setText('abc')
        dlg.confirm.edit.setText('abd')
        self.assertFalse(dlg.ok.isEnabled())
        self.assertTrue(dlg.error.isVisibleTo(dlg))
        dlg.confirm.edit.setText('abc')
        self.assertFalse(dlg.ok.isEnabled())
        dlg.ack.setChecked(True)
        self.assertTrue(dlg.ok.isEnabled())
        dlg.hint.setText('h' * 300)
        self.assertEqual(len(dlg.hint.text()), protocol.HINT_MAX_CHARS)
        self.assertEqual(dlg.values(), ('abc', 'h' * protocol.HINT_MAX_CHARS))

    def test_change_password_dialog_validation(self):
        dlg = dialogs.ChangePasswordDialog('Demo', 'old hint')
        self.assertEqual(dlg.hint.text(), 'old hint')
        dlg.old.edit.setText('a')
        dlg.new.edit.setText('b')
        dlg.confirm.edit.setText('b')
        self.assertTrue(dlg.ok.isEnabled())
        self.assertEqual(dlg.values(), ('a', 'b', 'old hint'))

    def test_remove_password_dialog_requires_ack(self):
        dlg = dialogs.RemovePasswordDialog('Demo')
        dlg.old.edit.setText('a')
        self.assertFalse(dlg.ok.isEnabled())
        dlg.ack.setChecked(True)
        self.assertTrue(dlg.ok.isEnabled())

    def test_erase_dialog_requires_typed_word(self):
        dlg = dialogs.EraseDialog('Demo', 'WX1…5678', [('exfat', 'exFAT')])
        self.assertFalse(dlg.ok.isEnabled())
        dlg.typed.setText('erase')
        self.assertFalse(dlg.ok.isEnabled())
        dlg.typed.setText('ERASE')
        self.assertTrue(dlg.ok.isEnabled())
        self.assertEqual(dlg.values(), ('exfat', 'My Passport'))
        dlg.format.setCurrentIndex(0)
        self.assertEqual(dlg.values()[0], '')

    def test_format_dialog_requires_typed_word_and_label(self):
        dlg = dialogs.FormatDialog('Demo', [('ntfs', 'NTFS'), ('ext4', 'ext4')], 'Old name')
        self.assertEqual(dlg.label_edit.text(), 'Old name')
        dlg.typed.setText('FORMAT')
        self.assertTrue(dlg.ok.isEnabled())
        dlg.label_edit.setText('  ')
        self.assertFalse(dlg.ok.isEnabled())
        dlg.label_edit.setText('Fresh')
        dlg.format.setCurrentIndex(1)
        self.assertEqual(dlg.values(), ('ext4', 'Fresh'))

    def test_password_field_show_toggle(self):
        from PyQt5.QtWidgets import QLineEdit
        from wdpassport.ui.widgets import PasswordField
        field = PasswordField()
        self.assertEqual(field.edit.echoMode(), QLineEdit.Password)
        field.show.setChecked(True)
        self.assertEqual(field.edit.echoMode(), QLineEdit.Normal)


if __name__ == '__main__':
    unittest.main(verbosity=2)
