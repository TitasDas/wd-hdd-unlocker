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

LIGHT_STYLE = '''
QFrame#rootFrame { background-color: #eef2f6; }
QFrame#headerCard {
    border-radius: 12px;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #0f2a44, stop: 1 #0b1f33);
}
QLabel#titleLabel { color: #ffffff; font-size: 28px; font-weight: 700; }
QLabel#subtitleLabel { color: #c9d7ea; font-size: 13px; }
QLabel#chipLabel, QLabel#stateChip {
    border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 700;
    border: 1px solid #c2d5f0; background: #e2ecf9; color: #153a63;
}
QFrame#panelCard {
    border: 1px solid #dce3ec;
    border-radius: 10px;
    background: #ffffff;
}
QLabel#sectionTitle { color: #102d4d; font-size: 14px; font-weight: 700; }
QLabel#fieldLabel { color: #26435f; font-size: 12px; font-weight: 600; }
QLineEdit {
    border: 1px solid #b8c6d8; border-radius: 8px; padding: 8px 10px;
    background: #ffffff; color: #20374f;
}
QLineEdit:focus { border: 1px solid #2e5e92; background: #fafcff; }
QCheckBox { color: #26435f; }
QPushButton { border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton#primaryBtn { background: #1f4f82; color: #ffffff; }
QPushButton#primaryBtn:hover { background: #1b456f; }
QPushButton#primaryBtn:pressed { background: #173a5d; }
QPushButton#secondaryBtn { background: #5f7898; color: #ffffff; }
QPushButton#secondaryBtn:hover { background: #526a89; }
QPushButton#secondaryBtn:pressed { background: #465b77; }
QPushButton#neutralBtn { background: #eff3f8; color: #2a4864; border: 1px solid #ced9e6; }
QPushButton#neutralBtn:hover { background: #e4ebf4; }
QPushButton#neutralBtn:pressed { background: #d9e3ef; }
QPushButton#dangerBtn { background: #b84a4a; color: #ffffff; }
QPushButton#dangerBtn:hover { background: #a44141; }
QPushButton#dangerBtn:pressed { background: #8e3737; }
QPushButton:disabled { background: #c5ced9; color: #eef2f8; }
QTextEdit {
    border: 1px solid #d5dee8; border-radius: 8px;
    background: #fcfdfe; color: #20374f; padding: 8px;
}
'''

DARK_STYLE = '''
QFrame#rootFrame { background-color: #0f141b; }
QFrame#headerCard {
    border-radius: 12px;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #16355d, stop: 1 #0b1f35);
}
QLabel#titleLabel { color: #f3f7ff; font-size: 28px; font-weight: 700; }
QLabel#subtitleLabel { color: #b9cde8; font-size: 13px; }
QLabel#chipLabel, QLabel#stateChip {
    border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 700;
    border: 1px solid #37557a; background: #1a2c43; color: #dbeaff;
}
QFrame#panelCard {
    border: 1px solid #2a3644;
    border-radius: 10px;
    background: #171f29;
}
QLabel#sectionTitle { color: #e8eef9; font-size: 14px; font-weight: 700; }
QLabel#fieldLabel { color: #d2dfef; font-size: 12px; font-weight: 600; }
QLineEdit {
    border: 1px solid #45586f; border-radius: 8px; padding: 8px 10px;
    background: #101722; color: #e7eef9;
}
QLineEdit:focus { border: 1px solid #5e8fca; background: #111d2c; }
QCheckBox { color: #c7d7ea; }
QPushButton { border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton#primaryBtn { background: #2b6cb2; color: #ffffff; }
QPushButton#primaryBtn:hover { background: #255f9c; }
QPushButton#primaryBtn:pressed { background: #205283; }
QPushButton#secondaryBtn { background: #4f6785; color: #eef5ff; }
QPushButton#secondaryBtn:hover { background: #445b77; }
QPushButton#secondaryBtn:pressed { background: #3a4f68; }
QPushButton#neutralBtn { background: #233344; color: #d9e8fb; border: 1px solid #39526c; }
QPushButton#neutralBtn:hover { background: #273c52; }
QPushButton#neutralBtn:pressed { background: #203246; }
QPushButton#dangerBtn { background: #a84a4a; color: #ffffff; }
QPushButton#dangerBtn:hover { background: #934141; }
QPushButton#dangerBtn:pressed { background: #7e3737; }
QPushButton:disabled { background: #2b3643; color: #7d8ea3; }
QTextEdit {
    border: 1px solid #334354; border-radius: 8px;
    background: #101722; color: #dce7f5; padding: 8px;
}
'''


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
        self.current_theme = 'light'
        self.current_state = 'READY'

        frame.setObjectName('rootFrame')
        frame.resize(900, 640)
        frame.setMinimumSize(780, 560)
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)

        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Header
        header_card = QFrame()
        header_card.setObjectName('headerCard')
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)

        title_group = QVBoxLayout()
        self.title_label = QLabel('WD My Passport Linux Unlocker')
        self.title_label.setObjectName('titleLabel')
        self.subtitle_label = QLabel('Unlock and mount WD My Passport / Ultra drives on Linux')
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
        self.mount_btn.setObjectName('secondaryBtn')
        self.mount_btn.setEnabled(False)
        self.mount_btn.clicked.connect(self.mount_wd)
        self.mount_btn.setShortcut('Alt+M')
        self.mount_btn.setToolTip('Mount drive (Alt+M)')

        self.exit_btn = QPushButton('Exit')
        self.exit_btn.setObjectName('dangerBtn')
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
        self.clear_log_btn.setObjectName('neutralBtn')
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

        self.theme_btn = QPushButton('Dark Mode')
        self.theme_btn.setObjectName('neutralBtn')
        self.theme_btn.setCheckable(True)
        self.theme_btn.setToolTip('Toggle dark mode')
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setMinimumHeight(34)

        self.disclaimer_btn = QPushButton('Disclaimer')
        self.disclaimer_btn.setObjectName('neutralBtn')
        self.disclaimer_btn.clicked.connect(self.show_disclaimer)
        self.disclaimer_btn.setToolTip('Open disclaimer (F1)')
        self.disclaimer_btn.setMinimumHeight(34)

        footer_layout.addWidget(self.theme_btn)
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
        frame.setTabOrder(self.clear_log_btn, self.theme_btn)
        frame.setTabOrder(self.theme_btn, self.disclaimer_btn)
        frame.setTabOrder(self.disclaimer_btn, self.exit_btn)

        self.apply_texts(frame)

        self.pw_box.textChanged.connect(self.pw_box_text_changed)
        self.pw_box.returnPressed.connect(self.pw_box_check_text)
        self.pw_box.setFocus()

        self.check_wd_drive()

    def apply_texts(self, frame):
        frame.setWindowTitle('WD My Passport Linux Unlocker')
        self.decrypt_btn.setEnabled(False)
        self.apply_theme('light')
        self.set_state('READY')

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        if theme_name == 'dark':
            self.frame.setStyleSheet(DARK_STYLE)
            self.theme_btn.setText('Light Mode')
            self.theme_btn.setChecked(True)
        else:
            self.frame.setStyleSheet(LIGHT_STYLE)
            self.theme_btn.setText('Dark Mode')
            self.theme_btn.setChecked(False)
        self.set_state(self.current_state)

    def toggle_theme(self):
        if self.current_theme == 'light':
            self.apply_theme('dark')
        else:
            self.apply_theme('light')

    def show_error(self, title, message):
        self.set_state('ERROR')
        self.append_log(message)
        QMessageBox.warning(self.frame, title, message)

    def set_state(self, value):
        state = value.upper()
        self.current_state = state
        self.state_chip.setText(state)

        light_palette = {
            'READY': ('#e7edf5', '#17395a', '#c9d6e6'),
            'WORKING': ('#fff3dc', '#724500', '#f4d6a4'),
            'MOUNT': ('#e9edf3', '#244566', '#cfd9e5'),
            'DONE': ('#e5f5e9', '#1f5a32', '#c8e5cf'),
            'WARN': ('#fff3dc', '#724500', '#f4d6a4'),
            'ERROR': ('#f9e6e6', '#712121', '#ebc7c7'),
            'WAITING': ('#e9edf3', '#244566', '#cfd9e5'),
            'CHECK': ('#e9edf3', '#244566', '#cfd9e5'),
        }
        dark_palette = {
            'READY': ('#1d324a', '#dbeaff', '#2f4b69'),
            'WORKING': ('#4e3f1f', '#ffe7ad', '#6b5730'),
            'MOUNT': ('#253546', '#dbe7f7', '#374b61'),
            'DONE': ('#20402b', '#d7f4df', '#336447'),
            'WARN': ('#4e3f1f', '#ffe7ad', '#6b5730'),
            'ERROR': ('#4b2626', '#ffd6d6', '#6a3838'),
            'WAITING': ('#253546', '#dbe7f7', '#374b61'),
            'CHECK': ('#253546', '#dbe7f7', '#374b61'),
        }

        palette = dark_palette if self.current_theme == 'dark' else light_palette
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

        # Continue with direct device checks instead of relying on lsblk label text,
        # which can vary across models and desktop environments.
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
            self.set_state('WARN')
            self.pw_box.setEnabled(False)
            self.decrypt_btn.setEnabled(False)
            self.mount_btn.setEnabled(False)
            self.append_log('Multiple WD block devices detected. Keep only one target WD drive connected.')
            self.append_log('Drive selection is ambiguous; reconnect and retry.')

    def get_partname(self):
        global PARTNAME

        disk_by_id = '/dev/disk/by-id'
        if not os.path.isdir(disk_by_id):
            PARTNAME = ''
            return 0

        partnames = []
        for entry in os.listdir(disk_by_id):
            if 'usb-wd' not in entry.lower():
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

    def resolve_mount_device(self, partname):
        """Return a mountable block device for a detected WD disk."""
        base_device = '/dev/' + partname
        out, _, rc = run_cmd(['lsblk', '-ln', '-o', 'NAME,TYPE', base_device])
        if rc == 0:
            for line in out.splitlines():
                fields = line.split()
                if len(fields) != 2:
                    continue
                name, dev_type = fields
                if dev_type == 'part':
                    return '/dev/' + name
        return base_device

    def find_existing_mount_target(self, devname):
        """Best-effort lookup for an existing mount target for WD device aliases."""
        candidates = {devname, os.path.realpath(devname)}

        if PARTNAME:
            disk_dev = "/dev/" + PARTNAME
            candidates.update({disk_dev, os.path.realpath(disk_dev)})
            out, _, rc = run_cmd(["lsblk", "-ln", "-o", "NAME", disk_dev])
            if rc == 0:
                for name in out.splitlines():
                    name = name.strip()
                    if not name:
                        continue
                    path = "/dev/" + name
                    candidates.update({path, os.path.realpath(path)})

        mounted_at, _, rc = run_cmd(["findmnt", "-n", "-o", "TARGET", "--source", devname])
        if rc == 0 and mounted_at.strip() and os.path.isdir(mounted_at.strip()):
            return mounted_at.strip()

        out, _, rc = run_cmd(["findmnt", "-rn", "-o", "SOURCE,TARGET"])
        if rc != 0:
            return ""

        for line in out.splitlines():
            fields = line.split(None, 1)
            if len(fields) != 2:
                continue
            source, target = fields
            source = source.strip().strip("[]")
            target = target.strip()
            if source in candidates or os.path.realpath(source) in candidates:
                if target and os.path.isdir(target):
                    return target

        return ""

    def decrypt_wd(self):
        self.call_cooking_pw()

    def create_password_blob(self, password):
        fd, path = tempfile.mkstemp(prefix='wdpass_')
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
        """Return currently connected SCSI generic devices of type 13 (enclosure services)."""
        sys_sg_root = '/sys/class/scsi_generic'
        if not os.path.isdir(sys_sg_root):
            return []

        devices = []
        for sg in sorted(os.listdir(sys_sg_root)):
            if not re.match(r'^sg\d+$', sg):
                continue

            type_path = os.path.join(sys_sg_root, sg, 'device', 'type')
            try:
                with open(type_path, 'r', encoding='utf-8') as fh:
                    scsi_type = fh.read().strip()
            except OSError:
                continue

            if scsi_type == '13':
                devices.append(sg)

        return devices

    def find_sg_for_partname(self):
        """Map detected WD block device (sdX) to matching sgX device."""
        global PARTNAME

        self.get_partname()
        if not PARTNAME:
            return None

        # Preferred path: /sys/block/sdX/device/scsi_generic/sgY
        sg_dir = os.path.join('/sys/block', PARTNAME, 'device', 'scsi_generic')
        if os.path.isdir(sg_dir):
            sgs = sorted([n for n in os.listdir(sg_dir) if re.match(r'^sg\d+$', n)])
            if sgs:
                return sgs[0]

        # Fallback: reverse mapping from sg -> block device.
        sys_sg_root = '/sys/class/scsi_generic'
        if os.path.isdir(sys_sg_root):
            for sg in sorted(os.listdir(sys_sg_root)):
                if not re.match(r'^sg\d+$', sg):
                    continue
                block_dir = os.path.join(sys_sg_root, sg, 'device', 'block')
                if not os.path.isdir(block_dir):
                    continue
                block_devices = os.listdir(block_dir)
                if PARTNAME in block_devices:
                    return sg

        return None


    def get_udev_id_path(self, devnode):
        try:
            out, _, rc = run_cmd(['udevadm', 'info', '--query=property', '--name', devnode])
        except FileNotFoundError:
            return ''
        if rc != 0:
            return ''
        for line in out.splitlines():
            if line.startswith('ID_PATH='):
                return line.split('=', 1)[1].strip()
        return ''

    def normalize_id_path(self, id_path):
        if not id_path:
            return ''
        if '-scsi-' in id_path:
            return id_path.split('-scsi-', 1)[0]
        return id_path

    def find_type13_sg_for_partname(self):
        global PARTNAME

        self.get_partname()
        if not PARTNAME:
            return []

        part_id_path = self.normalize_id_path(self.get_udev_id_path('/dev/' + PARTNAME))
        if not part_id_path:
            return []

        matched = []
        for sg in self.find_sg_devices():
            sg_id_path = self.normalize_id_path(self.get_udev_id_path('/dev/' + sg))
            if sg_id_path and sg_id_path == part_id_path:
                matched.append(sg)
        return matched

    def unlock_drive(self, payload_path):
        try:
            candidates = []

            matched_type13 = self.find_type13_sg_for_partname()
            if matched_type13:
                candidates.extend(matched_type13)
                self.append_log('Matched WD USB path candidates: ' + ', '.join('/dev/' + sg for sg in matched_type13))

            mapped_sg = self.find_sg_for_partname()
            if mapped_sg and mapped_sg not in candidates:
                candidates.append(mapped_sg)
                self.append_log('Mapped WD block device /dev/' + PARTNAME + ' to /dev/' + mapped_sg)

            # Last-resort fallback when path matching is unavailable.
            if not candidates:
                for sg in self.find_sg_devices():
                    if sg not in candidates:
                        candidates.append(sg)

            # Some bridges reject vendor commands on /dev/sgX but accept SG_IO on /dev/sdX.
            if PARTNAME and PARTNAME not in candidates:
                candidates.append(PARTNAME)

            if not candidates:
                self.show_error('Device Error', "Could not find a candidate device node for the WD drive.")
                return

            self.append_log('Unlock candidates: ' + ', '.join('/dev/' + dev for dev in candidates))

            unlock_ok = False
            last_detail = ''
            for dev in candidates:
                self.append_log('Trying unlock on /dev/' + dev + '...')
                cmd = ['sg_raw', '-s', '40', '-i', payload_path, '/dev/' + dev] + SCSI_UNLOCK_CMD
                out, err, rc = run_cmd(cmd)
                if rc == 0:
                    self.append_log('Secure hard drive identified at /dev/' + dev)
                    self.append_log('The WD drive is now unlocked and can be mounted!')
                    unlock_ok = True
                    break

                detail = (err or out or ('exit code ' + str(rc))).replace('\n', ' ').strip()
                last_detail = detail
                self.append_log('Unlock attempt failed on /dev/' + dev + ': ' + detail)

            if not unlock_ok:
                hint = ''
                if 'Illegal Request' in last_detail:
                    hint = ' The device rejected the vendor command. This can indicate endpoint/interface mismatch, unsupported model/firmware behavior, or password/key mismatch for this command path.'
                detail_msg = (' Details: ' + last_detail) if last_detail else ''
                self.show_error('Unlock Failed', 'SCSI decrypt command failed. Check password and connections.' + hint + detail_msg)
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

    def try_open_mount_path(self, mount_path):
        if not mount_path or not os.path.isdir(mount_path):
            return False

        open_attempts = []

        desktop_uid = os.environ.get('PKEXEC_UID')
        sudo_user = os.environ.get('SUDO_USER')

        if desktop_uid and is_executable_available('sudo'):
            open_attempts.extend([
                ['sudo', '-u', '#' + desktop_uid, 'xdg-open', mount_path],
                ['sudo', '-u', '#' + desktop_uid, 'gio', 'open', mount_path],
            ])
        elif sudo_user and is_executable_available('sudo'):
            open_attempts.extend([
                ['sudo', '-u', sudo_user, 'xdg-open', mount_path],
                ['sudo', '-u', sudo_user, 'gio', 'open', mount_path],
            ])

        open_attempts.extend([
            ['xdg-open', mount_path],
            ['gio', 'open', mount_path],
        ])

        for cmd in open_attempts:
            if not is_executable_available(cmd[0]):
                continue
            _, err, rc = run_cmd(cmd)
            if rc == 0:
                self.append_log('Opened mounted folder: ' + mount_path)
                return True
            if err:
                self.append_log('Open attempt failed (' + ' '.join(cmd[:2]) + '): ' + err)

        self.append_log('Could not auto-open mounted folder. Open manually: ' + mount_path)
        return False

    def mount_wd(self):
        global PARTNAME

        self.get_partname()
        if not PARTNAME:
            self.show_error('Mount Error', 'Cannot determine drive device name. Mount manually.')
            return

        run_cmd(['partprobe'])
        self.append_log('Available devices have been updated.')

        devname = self.resolve_mount_device(PARTNAME)
        self.append_log('Mounting device: ' + devname)

        # If already mounted, avoid re-mount attempts.
        mounted_at, _, findmnt_rc = run_cmd(['findmnt', '-n', '-o', 'TARGET', '--source', devname])
        if findmnt_rc == 0 and mounted_at.strip():
            if os.path.isdir(mounted_at.strip()):
                self.set_state('DONE')
                self.append_log('Drive is already mounted at: ' + mounted_at.strip())
                self.try_open_mount_path(mounted_at.strip())
                self.mount_btn.setEnabled(False)
                return
            self.append_log('Mounted target is invalid: ' + mounted_at.strip() + '. Re-mounting to a safe path...')
            run_cmd(['umount', devname])

        # Primary path: direct mount to avoid desktop auto-open popups on some environments.
        mount_dir = '/mnt/wd-security-' + PARTNAME
        if os.path.exists(mount_dir) and not os.path.isdir(mount_dir):
            mount_dir = '/mnt/wd-security-' + PARTNAME + '-mount'
        run_cmd(['mkdir', '-p', mount_dir])
        _, _, direct_rc = run_cmd(['mount', devname, mount_dir])

        if direct_rc == 0:
            self.set_state('DONE')
            self.append_log('WD hard drive decrypted and mounted successfully at: ' + mount_dir)
            self.try_open_mount_path(mount_dir)
            self.mount_btn.setEnabled(False)
            return

        # Fallback for environments where direct mount is restricted.
        _, _, mount_rc = run_cmd(['udisksctl', 'mount', '-b', devname, '--no-user-interaction'])
        if mount_rc == 0:
            mounted_at, _, findmnt_rc = run_cmd(['findmnt', '-n', '-o', 'TARGET', '--source', devname])
            if findmnt_rc == 0 and mounted_at.strip() and os.path.isdir(mounted_at.strip()):
                self.set_state('DONE')
                self.append_log('WD hard drive decrypted and mounted successfully at: ' + mounted_at.strip())
                self.try_open_mount_path(mounted_at.strip())
            else:
                detected_target = self.find_existing_mount_target(devname)
                if detected_target:
                    self.set_state('WARN')
                    self.append_log('Drive appears mounted despite a mount-path mismatch.')
                    self.append_log('Drive is accessible at: ' + detected_target)
                    self.try_open_mount_path(detected_target)
                else:
                    self.set_state('WARN')
                    self.append_log('Drive mounted but target path is invalid in the desktop view. Use /mnt/wd-security-' + PARTNAME)
        else:
            detected_target = self.find_existing_mount_target(devname)
            if detected_target:
                self.set_state('WARN')
                self.append_log('Mount command reported an error, but the drive is already accessible.')
                self.append_log('Drive is accessible at: ' + detected_target)
                self.try_open_mount_path(detected_target)
            else:
                self.set_state('WARN')
                self.append_log('Drive decrypted, but automount failed. Mount manually if needed.')

        self.mount_btn.setEnabled(False)

    def show_disclaimer(self):
        QMessageBox.information(
            self.frame,
            'Disclaimer',
            'Unofficial community utility. Not affiliated with or endorsed by '
            'Western Digital.\n\nUse only on drives you own or are explicitly '
            'authorized to access.\n\nThis utility enables temporary unlock for '
            'compatible WD Security drives and does not support permanent '
            'security removal.\n\nUse at your own risk. Always keep backups before '
            'using disk/security tools.\n\nFor safest operation, connect only one '
            'WD locked drive at a time.'
        )


def prompt_sudo():
    if os.geteuid() != 0:
        print('This program requires root permissions. Please run with sudo or pkexec.', file=sys.stderr)
        sys.exit(1)


def check_required_utils():
    required_bins = ['sg_raw', 'partprobe', 'lsusb', 'lsblk', 'findmnt', 'mount', 'umount', 'udisksctl', 'udevadm']
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
