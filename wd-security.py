#!/usr/bin/env python3
#
# WD Security unlock helper for Linux

import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QShortcut,
    QTextEdit,
    QVBoxLayout,
)

PARTNAME = ''
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKPW_PATH = os.path.join(SCRIPT_DIR, 'cookpw.py')
SCSI_UNLOCK_CMD = ['c1', 'e1', '00', '00', '00', '00', '00', '00', '28', '00']


def run_cmd(args, check=False):
    proc = subprocess.run(args, capture_output=True, text=True)
    out = (proc.stdout or '').strip()
    err = (proc.stderr or '').strip()
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, args, output=out + err)
    return out, err, proc.returncode


def is_executable_available(binary):
    return shutil.which(binary) is not None


class WDSecurityWindow:
    def setup_ui(self, frame):
        self.frame = frame
        frame.setObjectName('rootFrame')
        frame.resize(900, 640)
        frame.setMinimumSize(780, 560)
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        frame.setStyleSheet('''
            QFrame#rootFrame { background-color: palette(window); }
            QFrame#headerCard {
                border-radius: 12px;
                background: palette(dark);
            }
            QLabel#titleLabel {
                color: palette(bright-text);
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: palette(light);
                font-size: 13px;
            }
            QLabel#chipLabel,
            QLabel#stateChip {
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid palette(mid);
                background: palette(base);
                color: palette(text);
            }
            QFrame#panelCard {
                border: 1px solid palette(midlight);
                border-radius: 10px;
                background: palette(base);
            }
            QLabel#sectionTitle {
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#fieldLabel {
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit {
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 8px 10px;
            }
            QLineEdit:focus {
                border: 1px solid palette(highlight);
            }
            QPushButton {
                border-radius: 8px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton#primaryBtn {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QTextEdit {
                border: 1px solid palette(midlight);
                border-radius: 8px;
                padding: 8px;
            }
        ''')

        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Header
        header_card = QFrame()
        header_card.setObjectName('headerCard')
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)

        title_group = QVBoxLayout()
        self.title_label = QLabel('WD Security Unlocker')
        self.title_label.setObjectName('titleLabel')
        self.subtitle_label = QLabel('Unlock and mount compatible WD drives on Linux')
        self.subtitle_label.setObjectName('subtitleLabel')
        title_group.addWidget(self.title_label)
        title_group.addWidget(self.subtitle_label)

        self.chip_label = QLabel('Root access required')
        self.chip_label.setObjectName('chipLabel')
        self.chip_label.setAlignment(Qt.AlignCenter)
        self.chip_label.setMinimumWidth(170)

        header_layout.addLayout(title_group, 1)
        header_layout.addWidget(self.chip_label, 0, Qt.AlignTop)
        main_layout.addWidget(header_card)

        # Controls
        controls_card = QFrame()
        controls_card.setObjectName('panelCard')
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        controls_title = QLabel('Drive Access')
        controls_title.setObjectName('sectionTitle')
        controls_layout.addWidget(controls_title)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)

        self.pw_label = QLabel('Password')
        self.pw_label.setObjectName('fieldLabel')

        self.pw_box = QLineEdit()
        self.pw_box.setEchoMode(QLineEdit.Password)
        self.pw_box.setPlaceholderText('Enter password to unlock WD drive')
        self.pw_box.setAccessibleName('Drive password input')
        self.pw_box.setToolTip('Password used to unlock the connected WD drive')

        self.show_pw_check = QCheckBox('Show password')
        self.show_pw_check.stateChanged.connect(self.toggle_password_visibility)

        form_layout.addWidget(self.pw_label, 0, 0)
        form_layout.addWidget(self.pw_box, 0, 1)
        form_layout.addWidget(self.show_pw_check, 1, 1)
        form_layout.setColumnStretch(1, 1)
        controls_layout.addLayout(form_layout)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.decrypt_btn = QPushButton('Unlock Drive')
        self.decrypt_btn.setObjectName('primaryBtn')
        self.decrypt_btn.clicked.connect(self.decrypt_wd)
        self.decrypt_btn.setShortcut('Alt+U')
        self.decrypt_btn.setToolTip('Unlock drive (Alt+U)')

        self.mount_btn = QPushButton('Mount Drive')
        self.mount_btn.setEnabled(False)
        self.mount_btn.clicked.connect(self.mount_wd)
        self.mount_btn.setShortcut('Alt+M')
        self.mount_btn.setToolTip('Mount drive (Alt+M)')

        self.exit_btn = QPushButton('Exit')
        self.exit_btn.clicked.connect(frame.close)
        self.exit_btn.setToolTip('Close app (Esc)')

        for btn in (self.decrypt_btn, self.mount_btn, self.exit_btn):
            btn.setMinimumHeight(40)

        action_layout.addWidget(self.decrypt_btn)
        action_layout.addWidget(self.mount_btn)
        action_layout.addStretch(1)
        action_layout.addWidget(self.exit_btn)
        controls_layout.addLayout(action_layout)

        main_layout.addWidget(controls_card)

        # Status
        status_card = QFrame()
        status_card.setObjectName('panelCard')
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)

        status_header = QHBoxLayout()
        status_title = QLabel('Status & Activity')
        status_title.setObjectName('sectionTitle')

        self.state_chip = QLabel('READY')
        self.state_chip.setObjectName('stateChip')
        self.state_chip.setAlignment(Qt.AlignCenter)
        self.state_chip.setMinimumWidth(92)

        self.clear_log_btn = QPushButton('Clear')
        self.clear_log_btn.clicked.connect(self.clear_logs)
        self.clear_log_btn.setShortcut('Ctrl+L')
        self.clear_log_btn.setToolTip('Clear log (Ctrl+L)')
        self.clear_log_btn.setMinimumHeight(34)
        self.clear_log_btn.setMinimumWidth(84)

        status_header.addWidget(status_title)
        status_header.addStretch(1)
        status_header.addWidget(self.state_chip)
        status_header.addWidget(self.clear_log_btn)
        status_layout.addLayout(status_header)

        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setMinimumHeight(220)
        self.message_box.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.message_box.setAccessibleName('Status log output')
        status_layout.addWidget(self.message_box)

        main_layout.addWidget(status_card, 1)

        # Footer
        footer_layout = QHBoxLayout()
        self.disclaimer_btn = QPushButton('Disclaimer')
        self.disclaimer_btn.clicked.connect(self.show_disclaimer)
        self.disclaimer_btn.setToolTip('Open disclaimer (F1)')
        self.disclaimer_btn.setMinimumHeight(34)
        footer_layout.addWidget(self.disclaimer_btn)
        footer_layout.addStretch(1)
        main_layout.addLayout(footer_layout)

        # Global shortcuts
        QShortcut(QKeySequence('Esc'), frame, activated=frame.close)
        QShortcut(QKeySequence('F1'), frame, activated=self.show_disclaimer)

        # Keyboard tab order
        frame.setTabOrder(self.pw_box, self.show_pw_check)
        frame.setTabOrder(self.show_pw_check, self.decrypt_btn)
        frame.setTabOrder(self.decrypt_btn, self.mount_btn)
        frame.setTabOrder(self.mount_btn, self.clear_log_btn)
        frame.setTabOrder(self.clear_log_btn, self.disclaimer_btn)
        frame.setTabOrder(self.disclaimer_btn, self.exit_btn)

        self.apply_texts(frame)

        self.pw_box.textChanged.connect(self.pw_box_text_changed)
        self.pw_box.returnPressed.connect(self.pw_box_check_text)
        self.pw_box.setFocus()

        self.check_wd_drive()

    def apply_texts(self, frame):
        frame.setWindowTitle('WD Security for Linux')
        self.decrypt_btn.setEnabled(False)
        self.set_state('READY')

    def show_error(self, title, message):
        self.set_state('ERROR')
        self.append_log(message)
        QMessageBox.warning(self.frame, title, message)

    def set_state(self, value):
        state = value.upper()
        self.state_chip.setText(state)

        palette = {
            'READY': ('#e7edf5', '#17395a', '#c9d6e6'),
            'WORKING': ('#fff3dc', '#724500', '#f4d6a4'),
            'MOUNT': ('#e9edf3', '#244566', '#cfd9e5'),
            'DONE': ('#e5f5e9', '#1f5a32', '#c8e5cf'),
            'WARN': ('#fff3dc', '#724500', '#f4d6a4'),
            'ERROR': ('#f9e6e6', '#712121', '#ebc7c7'),
            'WAITING': ('#e9edf3', '#244566', '#cfd9e5'),
            'CHECK': ('#e9edf3', '#244566', '#cfd9e5'),
        }
        bg, fg, bd = palette.get(state, palette['READY'])
        self.state_chip.setStyleSheet(
            f'color: {fg}; background: {bg}; border: 1px solid {bd}; border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 700;'
        )

    def append_log(self, msg):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.message_box.append(f'[{stamp}] {msg}')

    def toggle_password_visibility(self, state):
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.pw_box.setEchoMode(mode)

    def clear_logs(self):
        self.message_box.clear()
        self.set_state('READY')

    def pw_box_text_changed(self, text):
        self.decrypt_btn.setEnabled(bool(text))

    def pw_box_check_text(self):
        if self.pw_box.text():
            self.decrypt_wd()
        else:
            self.pw_box.setFocus()

    def check_wd_drive(self):
        out, _, _ = run_cmd(['lsusb'])
        wd_usb_lines = [line for line in out.splitlines() if 'western digital' in line.lower()]

        if not wd_usb_lines:
            self.set_state('WAITING')
            self.append_log('No Western Digital drive attached.')
            self.append_log('Attach a compatible drive and restart.')
            self.pw_box.setEnabled(False)
            return

        for line in wd_usb_lines:
            self.append_log('Western Digital drive found at: ' + line)

        lsblk_out, _, _ = run_cmd(['lsblk'])
        if 'wd unlocker' not in lsblk_out.lower():
            self.set_state('CHECK')
            self.append_log("Drive may already be unlocked or not WD Security compatible.")
            self.append_log('Reconnect the disk and try again if needed.')
            self.pw_box.setEnabled(False)
            return

        self.set_state('READY')
        self.append_log('Checking drive lock status...')
        self.check_unlock_status()

    def check_unlock_status(self):
        global PARTNAME

        num_lines = self.get_partname()
        if num_lines == 0:
            self.show_error('Drive Detection Error', 'Could not locate WD drive. Reconnect and retry.')
        elif num_lines == 1:
            self.append_log('Drive appears to be locked.')
        else:
            self.set_state('MOUNT')
            self.append_log('Drive appears to be already unlocked.')
            self.pw_box.setEnabled(False)
            self.append_log('Drive device name: ' + PARTNAME)
            self.check_mount_status()

    def get_partname(self):
        global PARTNAME

        disk_by_id = '/dev/disk/by-id'
        if not os.path.isdir(disk_by_id):
            PARTNAME = ''
            return 0

        partnames = []
        for entry in os.listdir(disk_by_id):
            if 'usb-WD' not in entry:
                continue
            full = os.path.join(disk_by_id, entry)
            if not os.path.islink(full):
                continue
            try:
                target = os.path.realpath(full)
            except OSError:
                continue
            base = os.path.basename(target)
            if re.match(r'^sd[a-z]+$', base):
                partnames.append(base)

        partnames = sorted(set(partnames))
        PARTNAME = partnames[0] if partnames else ''
        return len(partnames)

    def check_mount_status(self):
        self.mount_btn.setEnabled(True)

    def decrypt_wd(self):
        self.call_cooking_pw()

    def create_password_blob(self, password):
        fd, path = tempfile.mkstemp(prefix='wdpass_', dir=SCRIPT_DIR)
        os.close(fd)
        os.chmod(path, 0o600)

        proc = subprocess.run(
            [sys.executable, COOKPW_PATH, '--stdin'],
            input=password.encode('utf-8'),
            capture_output=True
        )

        if proc.returncode != 0:
            try:
                os.unlink(path)
            except OSError:
                pass
            stderr_text = (proc.stderr or b'').decode('utf-8', errors='replace').strip()
            raise RuntimeError(stderr_text or 'cookpw.py failed')

        with open(path, 'wb') as handle:
            handle.write(proc.stdout)

        return path

    def call_cooking_pw(self):
        self.set_state('WORKING')
        self.append_log('Preparing password payload...')
        QApplication.processEvents()

        password = self.pw_box.text()
        self.pw_box.clear()

        if not password:
            self.set_state('READY')
            self.append_log('Password cannot be empty.')
            return

        try:
            payload_path = self.create_password_blob(password)
        except Exception as exc:
            self.show_error('Payload Error', f'Cannot prepare password payload: {exc}')
            return

        self.append_log('Sending SCSI commands to unlock the drive...')
        self.unlock_drive(payload_path)

    def find_sg_devices(self):
        out, _, rc = run_cmd(['/bin/dmesg'])
        if rc != 0:
            return []

        devices = []
        for line in out.splitlines():
            if 'type 13' not in line:
                continue
            match = re.search(r'\b(sg\d+)\b', line)
            if match:
                devices.append(match.group(1))
        return sorted(set(devices))

    def unlock_drive(self, payload_path):
        try:
            sg_devices = self.find_sg_devices()
            if not sg_devices:
                self.show_error('Device Error', "Could not find an sg 'type 13' device in dmesg.")
                return

            if len(sg_devices) > 1:
                self.show_error('Device Conflict', "Multiple SCSI 'type 13' devices recognized. Unplug others and retry.")
                return

            sg_dev = sg_devices[0]
            self.append_log('Secure hard drive identified at /dev/' + sg_dev)

            cmd = ['sg_raw', '-s', '40', '-i', payload_path, '/dev/' + sg_dev] + SCSI_UNLOCK_CMD
            try:
                run_cmd(cmd, check=True)
                self.append_log('The WD drive is now unlocked and can be mounted!')
            except subprocess.CalledProcessError:
                self.show_error('Unlock Failed', 'SCSI decrypt command failed. Check password and connections.')
                return

            self.set_state('MOUNT')
            self.pw_box.setEnabled(False)
            self.decrypt_btn.setEnabled(False)
            self.mount_wd()
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass

    def mount_wd(self):
        global PARTNAME

        self.get_partname()
        if not PARTNAME:
            self.show_error('Mount Error', 'Cannot determine drive device name. Mount manually.')
            return

        run_cmd(['partprobe'])
        self.append_log('Available devices have been updated.')

        devname = '/dev/' + PARTNAME + '1'
        self.append_log('Mounting device: ' + devname)
        _, _, mount_rc = run_cmd(['udisksctl', 'mount', '-b', devname])

        if mount_rc == 0:
            self.set_state('DONE')
            self.append_log('WD hard drive decrypted and mounted successfully!')
        else:
            self.set_state('WARN')
            self.append_log('Drive decrypted, but automount failed. Mount manually if needed.')

        self.mount_btn.setEnabled(False)

    def show_disclaimer(self):
        QMessageBox.information(
            self.frame,
            'Disclaimer',
            'This utility enables temporary unlock for modern WD drives that support '
            'hardware-level link encryption.\nIt does not support permanent unlock '
            '(removing security) or initial locking.\n\nThis utility is not '
            'officially licensed by Western Digital.\n\nThis utility has only been '
            'tested with one WD locked drive attached.\nPlease do not connect more '
            'than one locked USB drive.'
        )


def prompt_sudo():
    if os.geteuid() != 0:
        print('This program requires root permissions. Please run with sudo or pkexec.', file=sys.stderr)
        sys.exit(1)


def check_required_utils():
    required_bins = ['sg_raw', 'partprobe', 'lsusb', 'lsblk', 'udisksctl']
    missing = [binary for binary in required_bins if not is_executable_available(binary)]
    if missing:
        print(f"Missing required system tools: {', '.join(missing)}")
        print('Please install the required packages and retry.')
        sys.exit(1)


if __name__ == '__main__':
    prompt_sudo()
    check_required_utils()

    app = QApplication(sys.argv)
    frame = QFrame()
    ui = WDSecurityWindow()
    ui.setup_ui(frame)
    frame.show()
    sys.exit(app.exec_())
