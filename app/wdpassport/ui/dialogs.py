"""Modal dialogs for password management, erase confirmation and about."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout,
)

from .. import APP_NAME, VERSION
from ..protocol import HINT_MAX_CHARS
from .widgets import PasswordField, label


class _BaseDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 18, 20, 18)
        self.layout_.setSpacing(12)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignLeft)
        self.form.setVerticalSpacing(10)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok = self.buttons.button(QDialogButtonBox.Ok)
        self.ok.setObjectName('primary')
        self.buttons.button(QDialogButtonBox.Cancel).setObjectName('secondary')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.error = QLabel('')
        self.error.setObjectName('dangerText')
        self.error.setWordWrap(True)
        self.error.hide()

    def finish_layout(self, intro=''):
        if intro:
            self.layout_.addWidget(label(intro, 'cardSub'))
        self.layout_.addLayout(self.form)
        self.layout_.addWidget(self.error)
        self.layout_.addWidget(self.buttons)

    def fail(self, text):
        self.error.setText(text)
        self.error.show()


class SetPasswordDialog(_BaseDialog):
    def __init__(self, drive_name, parent=None):
        super().__init__('Set password', parent)
        self.new = PasswordField('New password')
        self.confirm = PasswordField('Repeat new password')
        self.hint = QLineEdit()
        self.hint.setMaxLength(HINT_MAX_CHARS)
        self.hint.setPlaceholderText('Optional. Shown to anyone who plugs the drive in.')
        self.ack = QCheckBox('I understand that a forgotten password cannot be recovered. '
                             'Erasing the drive is the only way back in.')
        self.form.addRow('New password', self.new)
        self.form.addRow('Confirm', self.confirm)
        self.form.addRow('Hint', self.hint)
        self.finish_layout('Turn on password protection for %s. After this, the drive asks for the password '
                           'every time it is plugged in, on any computer.' % drive_name)
        self.layout_.insertWidget(self.layout_.count() - 2, self.ack)
        self.ok.setText('Set password')
        self.ok.setEnabled(False)
        for w in (self.new.edit, self.confirm.edit):
            w.textChanged.connect(self._validate)
        self.ack.toggled.connect(self._validate)

    def _validate(self):
        ok = bool(self.new.text()) and self.new.text() == self.confirm.text() and self.ack.isChecked()
        self.ok.setEnabled(ok)
        if self.new.text() and self.confirm.text() and self.new.text() != self.confirm.text():
            self.fail('Passwords do not match.')
        else:
            self.error.hide()

    def values(self):
        return self.new.text(), self.hint.text().strip()


class ChangePasswordDialog(_BaseDialog):
    def __init__(self, drive_name, current_hint='', parent=None):
        super().__init__('Change password', parent)
        self.old = PasswordField('Current password')
        self.new = PasswordField('New password')
        self.confirm = PasswordField('Repeat new password')
        self.hint = QLineEdit(current_hint)
        self.hint.setMaxLength(HINT_MAX_CHARS)
        self.hint.setPlaceholderText('Optional')
        self.form.addRow('Current password', self.old)
        self.form.addRow('New password', self.new)
        self.form.addRow('Confirm', self.confirm)
        self.form.addRow('Hint', self.hint)
        self.finish_layout('Change the password on %s. The drive stays unlocked until it is ejected.' % drive_name)
        self.ok.setText('Change password')
        self.ok.setEnabled(False)
        for w in (self.old.edit, self.new.edit, self.confirm.edit):
            w.textChanged.connect(self._validate)

    def _validate(self):
        ok = bool(self.old.text()) and bool(self.new.text()) and self.new.text() == self.confirm.text()
        self.ok.setEnabled(ok)
        if self.new.text() and self.confirm.text() and self.new.text() != self.confirm.text():
            self.fail('New passwords do not match.')
        else:
            self.error.hide()

    def values(self):
        return self.old.text(), self.new.text(), self.hint.text().strip()


class RemovePasswordDialog(_BaseDialog):
    def __init__(self, drive_name, parent=None):
        super().__init__('Remove password', parent)
        self.old = PasswordField('Current password')
        self.ack = QCheckBox('I understand the drive will open without a password on any computer.')
        self.form.addRow('Current password', self.old)
        self.finish_layout('Turn off password protection for %s. The data stays encrypted on disk but the drive '
                           'unlocks itself automatically.' % drive_name)
        self.layout_.insertWidget(self.layout_.count() - 2, self.ack)
        self.ok.setText('Remove password')
        self.ok.setObjectName('danger')
        self.ok.setEnabled(False)
        self.old.edit.textChanged.connect(self._validate)
        self.ack.toggled.connect(self._validate)

    def _validate(self):
        self.ok.setEnabled(bool(self.old.text()) and self.ack.isChecked())

    def values(self):
        return self.old.text()


class EraseDialog(_BaseDialog):
    def __init__(self, drive_name, serial, formats, parent=None):
        super().__init__('Erase drive', parent)
        self.setMinimumWidth(520)
        self.format = QComboBox()
        self.format.addItem('Do not format (I will partition it myself)', '')
        for fstype, text in formats:
            self.format.addItem(text, fstype)
        if self.format.count() > 1:
            self.format.setCurrentIndex(1)
        self.label_edit = QLineEdit('My Passport')
        self.label_edit.setMaxLength(32)
        self.typed = QLineEdit()
        self.typed.setPlaceholderText('Type ERASE to confirm')
        self.form.addRow('After erasing', self.format)
        self.form.addRow('New volume name', self.label_edit)
        self.form.addRow('Confirmation', self.typed)
        warning = label('This resets the encryption key on %s (serial %s). Every file on it becomes unreadable '
                        'instantly and permanently. No recovery tool can bring it back.\n\n'
                        'Use this when the password is lost, or to wipe the drive before handing it on.'
                        % (drive_name, serial or 'unknown'), 'dangerText')
        self.finish_layout()
        self.layout_.insertWidget(0, warning)
        self.ok.setText('Erase everything')
        self.ok.setObjectName('danger')
        self.ok.setEnabled(False)
        self.typed.textChanged.connect(lambda t: self.ok.setEnabled(t.strip() == 'ERASE'))

    def values(self):
        return self.format.currentData(), self.label_edit.text().strip()


class FormatDialog(_BaseDialog):
    def __init__(self, drive_name, formats, current_label='', parent=None):
        super().__init__('Format drive', parent)
        self.setMinimumWidth(520)
        self.format = QComboBox()
        for fstype, text in formats:
            self.format.addItem(text, fstype)
        self.label_edit = QLineEdit(current_label or 'My Passport')
        self.label_edit.setMaxLength(32)
        self.typed = QLineEdit()
        self.typed.setPlaceholderText('Type FORMAT to confirm')
        self.form.addRow('Filesystem', self.format)
        self.form.addRow('Volume name', self.label_edit)
        self.form.addRow('Confirmation', self.typed)
        warning = label('Formatting %s deletes every file on it. The password and encryption key stay as they are.'
                        % drive_name, 'dangerText')
        self.finish_layout()
        self.layout_.insertWidget(0, warning)
        self.ok.setText('Format')
        self.ok.setObjectName('danger')
        self.ok.setEnabled(False)
        self.typed.textChanged.connect(self._validate)
        self.label_edit.textChanged.connect(self._validate)

    def _validate(self):
        self.ok.setEnabled(self.typed.text().strip() == 'FORMAT' and bool(self.label_edit.text().strip())
                           and self.format.count() > 0)

    def values(self):
        return self.format.currentData(), self.label_edit.text().strip()


def confirm(parent, title, text, ok_text='Continue', danger=False):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    ok = box.addButton(ok_text, QMessageBox.AcceptRole)
    ok.setObjectName('danger' if danger else 'primary')
    cancel = box.addButton('Cancel', QMessageBox.RejectRole)
    cancel.setObjectName('secondary')
    box.setDefaultButton(cancel)
    box.exec_()
    return box.clickedButton() is ok


def show_about(parent):
    QMessageBox.about(
        parent, 'About',
        '<b>%s</b> %s<br><br>'
        'Unofficial community utility for WD My Passport, My Passport Ultra, easystore and Elements drives '
        'that use WD Security. Unlock, mount, set or change the password, remove it, safely eject, and erase.<br><br>'
        'Not affiliated with, endorsed by, or licensed by Western Digital. WD and My Passport are trademarks of '
        'their owners.<br><br>'
        'Use only on drives you own or are authorised to administer. Keep backups. '
        'See the bundled DISCLAIMER, TERMS and LEGAL_USE documents.<br><br>'
        'Based on prior work by KenMacD/wdpassport-utils and contributors (see NOTICE).'
        % (APP_NAME, VERSION))
