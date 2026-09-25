"""The main window: sidebar navigation, drive pages and the activity console."""

import platform
from datetime import datetime

from PyQt5.QtCore import QObject, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QShortcut,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import APP_NAME, VERSION, protocol
from ..devices import human_size, which
from ..manager import OperationError
from . import icons, theme
from .dialogs import (
    ChangePasswordDialog, EraseDialog, RemovePasswordDialog, SetPasswordDialog, confirm, show_about,
)
from .widgets import Card, KeyValueGrid, PasswordField, Pill, hrow, label

NAV = [
    ('drive', 'Drive', 'drive'),
    ('unlock', 'Unlock', 'unlock'),
    ('security', 'Password', 'key'),
    ('advanced', 'Advanced', 'settings'),
    ('activity', 'Activity', 'list'),
]

PAGE_TITLES = {
    'drive': ('Drive', 'Status, volumes and quick actions'),
    'unlock': ('Unlock', 'Enter the drive password to open it'),
    'security': ('Password', 'Set, change or remove the drive password'),
    'advanced': ('Advanced', 'Erase, diagnostics and support information'),
    'activity': ('Activity', 'Everything the app did in this session'),
}


class Worker(QObject):
    """Runs one manager operation on a background thread."""

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args

    def run(self):
        try:
            result = self.fn(*self.args)
        except OperationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, never swallowed
            self.failed.emit('Unexpected error: %s: %s' % (type(exc).__name__, exc))
        else:
            self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, manager, demo=False):
        super().__init__()
        self.manager = manager
        self.demo = demo
        self.states = []
        self.current = None
        self.tokens = theme.LIGHT
        self.theme_name = 'light'
        self.busy = False
        self._thread = None
        self._worker = None
        self.pills = []
        self.setWindowTitle(APP_NAME)
        self.resize(1080, 700)
        self.setMinimumSize(900, 600)
        self._build()
        self.manager.set_logger(self._log_from_thread)
        self.apply_theme('light')
        self.append_log('%s %s started%s' % (APP_NAME, VERSION, ' in demo mode (simulated drive)' if demo else ''))
        self.refresh()

    # --- construction ---------------------------------------------------------------

    def _build(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.pages = {}
        for key, builder in (
            ('drive', self._build_drive_page),
            ('unlock', self._build_unlock_page),
            ('security', self._build_security_page),
            ('advanced', self._build_advanced_page),
            ('activity', self._build_activity_page),
        ):
            page = builder()
            self.pages[key] = page
            self.stack.addWidget(page)
        content.addWidget(self.stack, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        content.addWidget(self.progress)

        outer.addLayout(content, 1)

        self.status_label = QLabel('Ready')
        self.statusBar().addWidget(self.status_label, 1)

        QShortcut(QKeySequence('F5'), self, activated=self.refresh)
        QShortcut(QKeySequence('F1'), self, activated=lambda: show_about(self))
        QShortcut(QKeySequence('Ctrl+Q'), self, activated=self.close)

    def _build_sidebar(self):
        bar = QFrame()
        bar.setObjectName('sidebar')
        bar.setFixedWidth(224)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        self.brand_icon = QLabel()
        self.brand_icon.setPixmap(icons.pixmap('shield', '#ffffff', 26, self.devicePixelRatioF()))
        text = QVBoxLayout()
        text.setSpacing(0)
        t1 = QLabel('WD My Passport')
        t1.setObjectName('brandTitle')
        t2 = QLabel('Linux Unlocker')
        t2.setObjectName('brandSub')
        text.addWidget(t1)
        text.addWidget(t2)
        brand.addWidget(self.brand_icon)
        brand.addLayout(text, 1)
        layout.addLayout(brand)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for key, text, icon_name in NAV:
            btn = QPushButton(text)
            btn.setObjectName('navBtn')
            btn.setCheckable(True)
            btn.setIconSize(QSize(18, 18))
            btn.setProperty('iconName', icon_name)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            layout.addWidget(btn)
        layout.addStretch(1)

        self.theme_btn = QPushButton('Dark mode')
        self.theme_btn.setObjectName('sideTool')
        self.theme_btn.setIconSize(QSize(16, 16))
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.about_btn = QPushButton('About and legal')
        self.about_btn.setObjectName('sideTool')
        self.about_btn.setIconSize(QSize(16, 16))
        self.about_btn.clicked.connect(lambda: show_about(self))
        layout.addWidget(self.theme_btn)
        layout.addWidget(self.about_btn)
        foot = QLabel('v%s · unofficial' % VERSION)
        foot.setObjectName('sidebarFoot')
        layout.addWidget(foot)
        return bar

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName('topbar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.page_title = QLabel('Drive')
        self.page_title.setObjectName('pageTitle')
        self.page_sub = QLabel('')
        self.page_sub.setObjectName('pageSubtitle')
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_sub)
        layout.addLayout(titles, 1)

        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(300)
        self.drive_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.drive_combo.currentIndexChanged.connect(self._drive_selected)
        self.top_pill = Pill('NO DRIVE', 'neutral')
        self.pills.append(self.top_pill)
        self.refresh_btn = QPushButton('Refresh')
        self.refresh_btn.setObjectName('secondary')
        self.refresh_btn.setToolTip('Rescan drives (F5)')
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.drive_combo)
        layout.addWidget(self.top_pill)
        layout.addWidget(self.refresh_btn)
        return bar

    def _scroll_page(self):
        area = QScrollArea()
        area.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)
        area.setWidget(inner)
        return area, layout

    def _build_drive_page(self):
        area, layout = self._scroll_page()

        self.empty_card = Card('No WD drive detected', 'Plug in a WD My Passport, My Passport Ultra, easystore or Elements '
                               'drive and press Refresh. Keep other WD drives unplugged while unlocking if you want '
                               'to be sure which one you are working on.')
        layout.addWidget(self.empty_card)

        self.details_card = Card('Drive details')
        top = QHBoxLayout()
        self.drive_title = QLabel('')
        self.drive_title.setObjectName('cardTitle')
        self.security_pill = Pill('', 'neutral')
        self.pills.append(self.security_pill)
        top.addWidget(self.drive_title, 1)
        top.addWidget(self.security_pill)
        self.details_card.body.removeWidget(self.details_card.title_label)
        self.details_card.title_label.deleteLater()
        self.details_card.body.insertLayout(0, top)
        self.kv = KeyValueGrid(columns=3)
        for key in ('Model', 'Capacity', 'Serial', 'Encryption', 'Security', 'Password hint',
                    'Disk node', 'Control node', 'USB ID'):
            self.kv.add(key, '', mono=key in ('Disk node', 'Control node', 'USB ID', 'Serial'))
        self.details_card.add(self.kv)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.act_unlock = QPushButton('Unlock and open')
        self.act_unlock.setObjectName('primary')
        self.act_unlock.clicked.connect(lambda: self.show_page('unlock'))
        self.act_mount = QPushButton('Mount')
        self.act_mount.setObjectName('primary')
        self.act_mount.clicked.connect(self.do_mount)
        self.act_open = QPushButton('Open folder')
        self.act_open.setObjectName('secondary')
        self.act_open.clicked.connect(self.do_open)
        self.act_eject = QPushButton('Eject and lock')
        self.act_eject.setObjectName('secondary')
        self.act_eject.clicked.connect(self.do_eject)
        for b in (self.act_unlock, self.act_mount, self.act_open, self.act_eject):
            actions.addWidget(b)
        actions.addStretch(1)
        self.details_card.add(actions)
        layout.addWidget(self.details_card)

        self.volumes_card = Card('Volumes', 'Partitions on the drive and where they are mounted. Files are mounted '
                                 'with your user as owner so you can copy, move and delete as normal.')
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Device', 'Filesystem', 'Label', 'Size', 'Mounted at'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMaximumHeight(140)
        self.table.setMinimumHeight(70)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.volumes_card.add(self.table)
        vol_actions = QHBoxLayout()
        self.act_write = QPushButton('Give me write access')
        self.act_write.setObjectName('secondary')
        self.act_write.setToolTip('For ext4 and similar filesystems: make your user the owner of the volume root')
        self.act_write.clicked.connect(self.do_grant_write)
        vol_actions.addWidget(self.act_write)
        vol_actions.addStretch(1)
        self.volumes_card.add(vol_actions)
        layout.addWidget(self.volumes_card)

        self.unsupported_card = Card('Drive does not answer security commands',
                                     'The drive is connected but did not respond to WD security commands on any '
                                     'device node. It may not be a WD Security model, or the USB bridge needs a '
                                     'different command path. Copy the diagnostics from the Advanced page and open '
                                     'a compatibility report.')
        layout.addWidget(self.unsupported_card)
        layout.addStretch(1)
        return area

    def _build_unlock_page(self):
        area, layout = self._scroll_page()
        self.unlock_card = Card('Enter password')
        self.unlock_intro = label('')
        self.unlock_card.add(self.unlock_intro)
        self.unlock_hint = label('', 'hint')
        self.unlock_card.add(self.unlock_hint)
        self.unlock_pw = PasswordField('Drive password')
        self.unlock_pw.edit.returnPressed.connect(self.do_unlock)
        self.unlock_pw.edit.textChanged.connect(self._update_actions)
        self.unlock_card.add(self.unlock_pw)
        row = QHBoxLayout()
        self.unlock_btn = QPushButton('Unlock and open')
        self.unlock_btn.setObjectName('primary')
        self.unlock_btn.setShortcut('Alt+U')
        self.unlock_btn.clicked.connect(self.do_unlock)
        row.addWidget(self.unlock_btn)
        row.addStretch(1)
        self.unlock_card.add(row)
        layout.addWidget(self.unlock_card)

        tips = Card('What happens next', 'The password is hashed the same way WD Security does it and sent to the '
                    'drive over USB. On success the volumes are mounted for your user and the folder opens in '
                    'your file manager. The drive locks itself again when it loses power, so use "Eject and lock" '
                    'when you are done.')
        layout.addWidget(tips)
        layout.addStretch(1)
        return area

    def _build_security_page(self):
        area, layout = self._scroll_page()
        self.sec_state = label('', 'cardSub')
        layout.addWidget(self.sec_state)

        self.set_card = Card('Set a password', 'Turn on password protection. The drive will ask for it on every '
                             'computer it is plugged into, including Windows and macOS with WD Security.')
        self.set_btn = QPushButton('Set password')
        self.set_btn.setObjectName('primary')
        self.set_btn.clicked.connect(self.do_set_password)
        self.set_card.add(hrow(self.set_btn, 'stretch'))
        layout.addWidget(self.set_card)

        self.change_card = Card('Change the password', 'Requires the current password. You can also update the hint.')
        self.change_btn = QPushButton('Change password')
        self.change_btn.setObjectName('primary')
        self.change_btn.clicked.connect(self.do_change_password)
        self.change_card.add(hrow(self.change_btn, 'stretch'))
        layout.addWidget(self.change_card)

        self.remove_card = Card('Remove the password', 'Turn off password protection. Data stays encrypted on the '
                                'platters but the drive opens without a password.')
        self.remove_btn = QPushButton('Remove password')
        self.remove_btn.setObjectName('danger')
        self.remove_btn.clicked.connect(self.do_remove_password)
        self.remove_card.add(hrow(self.remove_btn, 'stretch'))
        layout.addWidget(self.remove_card)
        layout.addStretch(1)
        return area

    def _build_advanced_page(self):
        area, layout = self._scroll_page()
        self.erase_card = Card('Erase drive', 'Resets the drive\'s encryption key, which makes every file unreadable '
                               'in an instant. Use it when the password is lost or before passing the drive on. '
                               'The password is removed and the drive can be formatted afresh.', danger=True)
        self.erase_btn = QPushButton('Erase everything')
        self.erase_btn.setObjectName('danger')
        self.erase_btn.clicked.connect(self.do_erase)
        self.erase_card.add(hrow(self.erase_btn, 'stretch'))
        layout.addWidget(self.erase_card)

        diag = Card('Diagnostics', 'If a drive is not recognised, copy this report into a compatibility issue on '
                    'GitHub. Serial numbers are masked.')
        self.diag_text = QPlainTextEdit()
        self.diag_text.setReadOnly(True)
        self.diag_text.setObjectName('console')
        self.diag_text.setMaximumHeight(200)
        diag.add(self.diag_text)
        self.diag_copy = QPushButton('Copy diagnostics')
        self.diag_copy.setObjectName('secondary')
        self.diag_copy.clicked.connect(self.copy_diagnostics)
        diag.add(hrow(self.diag_copy, 'stretch'))
        layout.addWidget(diag)
        layout.addStretch(1)
        return area

    def _build_activity_page(self):
        area, layout = self._scroll_page()
        card = Card('Activity log')
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName('console')
        self.console.setMinimumHeight(360)
        card.add(self.console, 1)
        clear = QPushButton('Clear')
        clear.setObjectName('secondary')
        clear.clicked.connect(self.console.clear)
        copy = QPushButton('Copy log')
        copy.setObjectName('secondary')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.console.toPlainText()))
        card.add(hrow(clear, copy, 'stretch'))
        layout.addWidget(card, 1)
        return area

    # --- theme --------------------------------------------------------------------

    def apply_theme(self, name):
        self.theme_name = name
        self.tokens = theme.DARK if name == 'dark' else theme.LIGHT
        self.setStyleSheet(theme.stylesheet(self.tokens))
        dpr = self.devicePixelRatioF()
        for key, btn in self.nav_buttons.items():
            color = self.tokens['icon_sidebar_active'] if btn.isChecked() else self.tokens['icon_sidebar']
            btn.setIcon(icons.icon(btn.property('iconName'), color, 18, dpr))
        self.theme_btn.setText('Light mode' if name == 'dark' else 'Dark mode')
        self.theme_btn.setIcon(icons.icon('sun' if name == 'dark' else 'moon', self.tokens['icon_sidebar'], 16, dpr))
        self.about_btn.setIcon(icons.icon('info', self.tokens['icon_sidebar'], 16, dpr))
        c = self.tokens['icon']
        self.refresh_btn.setIcon(icons.icon('refresh', c, 16, dpr))
        self.act_open.setIcon(icons.icon('folder', c, 16, dpr))
        self.act_eject.setIcon(icons.icon('eject', c, 16, dpr))
        self.act_write.setIcon(icons.icon('edit', c, 16, dpr))
        self.act_unlock.setIcon(icons.icon('unlock', '#ffffff', 16, dpr))
        self.act_mount.setIcon(icons.icon('drive', '#ffffff', 16, dpr))
        self.unlock_btn.setIcon(icons.icon('unlock', '#ffffff', 16, dpr))
        self.set_btn.setIcon(icons.icon('key', '#ffffff', 16, dpr))
        self.change_btn.setIcon(icons.icon('key', '#ffffff', 16, dpr))
        self.remove_btn.setIcon(icons.icon('trash', '#ffffff', 16, dpr))
        self.erase_btn.setIcon(icons.icon('warning', '#ffffff', 16, dpr))
        self.diag_copy.setIcon(icons.icon('copy', c, 16, dpr))
        for pill in self.pills:
            pill.apply_theme(self.tokens)

    def toggle_theme(self):
        self.apply_theme('light' if self.theme_name == 'dark' else 'dark')

    # --- navigation ---------------------------------------------------------------

    def show_page(self, key):
        self.stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)
        title, sub = PAGE_TITLES[key]
        self.page_title.setText(title)
        self.page_sub.setText(sub)
        dpr = self.devicePixelRatioF()
        for k, btn in self.nav_buttons.items():
            color = self.tokens['icon_sidebar_active'] if k == key else self.tokens['icon_sidebar']
            btn.setIcon(icons.icon(btn.property('iconName'), color, 18, dpr))
        if key == 'unlock':
            self.unlock_pw.setFocus()
        if key == 'advanced':
            self.diag_text.setPlainText(self.diagnostics_text())

    # --- logging and status -----------------------------------------------------------

    def _log_from_thread(self, msg):
        # Manager callbacks arrive on the worker thread; the signal hops back to the UI thread.
        worker = self._worker
        if worker is not None:
            worker.log.emit(msg)
        else:
            self.append_log(msg)

    def append_log(self, msg):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.console.appendPlainText('[%s] %s' % (stamp, msg))
        self.status_label.setText(msg)

    def set_busy(self, busy, text=''):
        self.busy = busy
        self.progress.setVisible(busy)
        self.refresh_btn.setEnabled(not busy)
        self.drive_combo.setEnabled(not busy)
        if text:
            self.status_label.setText(text)
        self._update_actions()

    def run_async(self, fn, *args, on_done=None, busy_text='Working'):
        if self.busy:
            return
        self.set_busy(True, busy_text)
        self._thread = QThread(self)
        self._worker = Worker(fn, *args)
        self._worker.moveToThread(self._thread)
        self._worker.log.connect(self.append_log)

        def finished(result):
            self._finish_async()
            if on_done:
                on_done(result)

        def failed(message):
            self._finish_async()
            self.append_log(message)
            QMessageBox.warning(self, 'Operation failed', message)
            self.reload_current()

        self._worker.finished.connect(finished)
        self._worker.failed.connect(failed)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _finish_async(self):
        thread = self._thread
        worker = self._worker
        self._thread = None
        self._worker = None
        if thread is not None:
            thread.quit()
            thread.wait(2000)
        if worker is not None:
            worker.deleteLater()
        self.set_busy(False)

    # --- drive state --------------------------------------------------------------------

    def refresh(self):
        if self.busy:
            return
        self.run_async(self.manager.scan, on_done=self._scanned, busy_text='Scanning for WD drives')

    def _scanned(self, states):
        self.states = states or []
        selected_disk = self.current.drive.disk if self.current else None
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        for st in self.states:
            self.drive_combo.addItem('%s  \u00b7  %s  \u00b7  %s' % (st.drive.display_name, st.drive.node, st.drive.size_text), st.drive.disk)
        index = 0
        for i, st in enumerate(self.states):
            if st.drive.disk == selected_disk:
                index = i
        if self.states:
            self.drive_combo.setCurrentIndex(index)
        self.drive_combo.blockSignals(False)
        self.current = self.states[index] if self.states else None
        self.render()

    def _drive_selected(self, index):
        if 0 <= index < len(self.states):
            self.current = self.states[index]
            self.render()

    def reload_current(self):
        if self.current is None or self.busy:
            self.refresh()
            return
        self.run_async(self.manager.refresh, self.current, on_done=self._reloaded, busy_text='Reading drive status')

    def _reloaded(self, state):
        for i, st in enumerate(self.states):
            if st.drive.disk == state.drive.disk or st is self.current:
                self.states[i] = state
        self.current = state
        self.render()

    def render(self):
        st = self.current
        has = st is not None
        self.empty_card.setVisible(not has)
        self.details_card.setVisible(has and st.supported)
        self.volumes_card.setVisible(has and st.supported)
        self.unsupported_card.setVisible(has and not st.supported)
        if not has:
            self.top_pill.set('NO DRIVE', 'neutral')
            self.unlock_intro.setText('Plug in a WD drive and press Refresh.')
            self.unlock_hint.setText('')
            self.sec_state.setText('No drive selected.')
            self._update_actions()
            return
        d = st.drive
        if not st.supported:
            self.top_pill.set('UNSUPPORTED', 'warn')
            self.unlock_intro.setText('%s did not answer WD security commands.' % d.display_name)
            self.unlock_hint.setText('')
            self.sec_state.setText('This drive did not answer WD security commands, so password features are unavailable.')
            self._update_actions()
            return
        s = st.status
        kind = {protocol.STATUS_LOCKED: 'err', protocol.STATUS_LOCKED_BLOCKED: 'err',
                protocol.STATUS_UNLOCKED: 'ok', protocol.STATUS_NOT_PROTECTED: 'info'}.get(s.security, 'warn')
        pill_text = s.security_name.upper()
        self.top_pill.set(pill_text, kind)
        self.security_pill.set(pill_text, kind)
        self.drive_title.setText(d.display_name)
        self.kv.set('Model', d.model.replace('_', ' '))
        self.kv.set('Capacity', d.size_text)
        self.kv.set('Serial', d.masked_serial)
        self.kv.set('Encryption', s.cipher_name)
        self.kv.set('Security', s.security_name)
        self.kv.set('Password hint', st.hint or ('none' if s.has_password else 'not applicable'))
        self.kv.set('Disk node', d.node)
        self.kv.set('Control node', d.control_node)
        self.kv.set('USB ID', d.usb_id)

        self.table.setRowCount(0)
        for p in d.partitions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in enumerate((p.node, p.fstype or 'unknown', p.label, human_size(p.size), p.mountpoint or 'not mounted')):
                item = QTableWidgetItem(text)
                self.table.setItem(row, col, item)
        self.table.setFixedHeight(max(70, 34 + 32 * max(1, len(d.partitions))))
        if d.partitions:
            self.table.selectRow(0)

        if s.is_locked:
            self.unlock_intro.setText('%s is locked. Enter the password that was set with WD Security or this app.' % d.display_name)
            self.unlock_hint.setText('Hint: %s' % st.hint if st.hint else 'No hint stored on the drive.')
        elif s.is_accessible:
            self.unlock_intro.setText('%s is already %s.' % (d.display_name, s.security_name.lower()))
            self.unlock_hint.setText('Use the Drive page to mount, open or eject it.')
        else:
            self.unlock_intro.setText('%s reports %s.' % (d.display_name, s.security_name))
            self.unlock_hint.setText('')

        if s.security == protocol.STATUS_NOT_PROTECTED:
            self.sec_state.setText('%s has no password. Anyone can plug it in and read it.' % d.display_name)
        elif s.is_unlocked:
            self.sec_state.setText('%s is unlocked. You can change or remove its password now.' % d.display_name)
        elif s.is_locked:
            self.sec_state.setText('%s is locked. Unlock it first to change or remove the password.' % d.display_name)
        else:
            self.sec_state.setText('%s reports %s.' % (d.display_name, s.security_name))
        self._update_actions()

    def _update_actions(self):
        st = self.current
        ok = st is not None and st.supported and not self.busy
        s = st.status if ok else None
        locked = bool(s and s.is_locked)
        accessible = bool(s and s.is_accessible)
        mounted = bool(ok and st.drive.mounted_partitions)
        self.act_unlock.setVisible(locked)
        self.act_unlock.setEnabled(ok and s.security == protocol.STATUS_LOCKED)
        self.act_mount.setVisible(accessible and not mounted)
        self.act_mount.setEnabled(ok)
        self.act_open.setEnabled(mounted)
        self.act_eject.setEnabled(ok)
        self.act_write.setEnabled(mounted and self._selected_partition() is not None
                                  and (self._selected_partition().fstype or '').lower() in
                                  ('ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'f2fs'))
        self.unlock_pw.setEnabled(ok and s.security == protocol.STATUS_LOCKED)
        self.unlock_btn.setEnabled(ok and s.security == protocol.STATUS_LOCKED and bool(self.unlock_pw.text()))
        self.set_card.setVisible(bool(s and s.security == protocol.STATUS_NOT_PROTECTED) or s is None)
        self.set_btn.setEnabled(bool(ok and s.security == protocol.STATUS_NOT_PROTECTED))
        self.change_card.setVisible(bool(s and s.has_password) or s is None)
        self.change_btn.setEnabled(bool(ok and s.is_unlocked))
        self.remove_card.setVisible(bool(s and s.has_password) or s is None)
        self.remove_btn.setEnabled(bool(ok and s.is_unlocked))
        self.erase_btn.setEnabled(ok)
        for key in ('unlock', 'security', 'advanced'):
            self.nav_buttons[key].setEnabled(True)

    def _selected_partition(self):
        if self.current is None:
            return None
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        idx = rows[0].row()
        parts = self.current.drive.partitions
        return parts[idx] if 0 <= idx < len(parts) else None

    # --- actions ----------------------------------------------------------------------

    def do_unlock(self):
        if self.current is None or self.busy:
            return
        password = self.unlock_pw.text()
        if not password:
            self.unlock_pw.setFocus()
            return
        self.unlock_pw.clear()
        self.run_async(self.manager.unlock, self.current, password, on_done=self._mounted, busy_text='Unlocking')

    def do_mount(self):
        if self.current is None:
            return
        self.run_async(self.manager.mount, self.current, on_done=self._mounted, busy_text='Mounting')

    def _mounted(self, targets):
        if targets:
            self.manager.open_folder(targets[0])
        self.show_page('drive')
        self.reload_current()

    def do_open(self):
        if self.current is None:
            return
        part = self._selected_partition()
        target = part.mountpoint if part and part.mountpoint else ''
        if not target:
            mounted = self.current.drive.mounted_partitions
            target = mounted[0].mountpoint if mounted else ''
        if target:
            self.manager.open_folder(target)

    def do_eject(self):
        if self.current is None:
            return
        d = self.current.drive
        if not confirm(self, 'Eject and lock',
                       'Unmount %s and power it off? It relocks the moment it loses power. '
                       'Unplug and reconnect it to use it again.' % d.display_name, 'Eject and lock'):
            return
        self.run_async(self.manager.eject_and_lock, self.current, on_done=lambda _: self.refresh(), busy_text='Ejecting')

    def do_grant_write(self):
        part = self._selected_partition()
        if part is None or not part.mountpoint:
            return
        if not confirm(self, 'Give write access',
                       'Make your user the owner of the top folder of %s? This changes ownership metadata '
                       'on the drive itself, so other Linux systems will see the same owner.' % part.mountpoint,
                       'Change owner'):
            return
        self.run_async(self.manager.grant_write_access, part.mountpoint,
                       on_done=lambda _: self.reload_current(), busy_text='Changing owner')

    def do_set_password(self):
        if self.current is None:
            return
        dlg = SetPasswordDialog(self.current.drive.display_name, self)
        if dlg.exec_() != dlg.Accepted:
            return
        password, hint = dlg.values()
        self.run_async(self.manager.set_password, self.current, password, hint,
                       on_done=lambda _: self._after_password('Password set.'), busy_text='Setting password')

    def do_change_password(self):
        if self.current is None:
            return
        dlg = ChangePasswordDialog(self.current.drive.display_name, self.current.hint, self)
        if dlg.exec_() != dlg.Accepted:
            return
        old, new, hint = dlg.values()
        self.run_async(self.manager.change_password, self.current, old, new, hint,
                       on_done=lambda _: self._after_password('Password changed.'), busy_text='Changing password')

    def do_remove_password(self):
        if self.current is None:
            return
        dlg = RemovePasswordDialog(self.current.drive.display_name, self)
        if dlg.exec_() != dlg.Accepted:
            return
        old = dlg.values()
        self.run_async(self.manager.remove_password, self.current, old,
                       on_done=lambda _: self._after_password('Password removed.'), busy_text='Removing password')

    def _after_password(self, text):
        QMessageBox.information(self, 'Done', text)
        self.reload_current()

    def do_erase(self):
        if self.current is None:
            return
        formats = []
        for fstype, tool, text in (('exfat', 'mkfs.exfat', 'exFAT (works on Windows, macOS and Linux)'),
                                   ('ntfs', 'mkfs.ntfs', 'NTFS (Windows and Linux)'),
                                   ('ext4', 'mkfs.ext4', 'ext4 (Linux only)')):
            if self.demo or which(tool):
                formats.append((fstype, text))
        dlg = EraseDialog(self.current.drive.display_name, self.current.drive.masked_serial, formats, self)
        if dlg.exec_() != dlg.Accepted:
            return
        fstype, vol_label = dlg.values()
        if not confirm(self, 'Last check', 'Erase %s now? There is no undo.' % self.current.drive.display_name,
                       'Erase now', danger=True):
            return
        self.run_async(self.manager.erase, self.current, fstype, vol_label,
                       on_done=lambda _: self._after_password('Drive erased.'), busy_text='Erasing')

    # --- diagnostics ------------------------------------------------------------------

    def diagnostics_text(self):
        lines = ['%s %s' % (APP_NAME, VERSION),
                 'Kernel: %s' % platform.release(),
                 'Python: %s' % platform.python_version(),
                 'Transport: %s' % (getattr(self.manager.transport, 'last_used', None) or self.manager.transport.name),
                 'Desktop user: %s' % (self.manager.user.name if self.manager.user else 'none detected'),
                 'Tools: ' + ', '.join('%s=%s' % (t, 'yes' if which(t) else 'no') for t in
                                       ('sg_raw', 'udisksctl', 'partprobe', 'parted', 'mkfs.exfat', 'mkfs.ntfs', 'ntfs-3g'))]
        if self.current is None:
            lines.append('No drive selected.')
        else:
            d = self.current.drive
            lines += ['Drive: %s (%s)' % (d.display_name, d.model),
                      'USB ID: %s' % d.usb_id,
                      'Serial: %s' % d.masked_serial,
                      'Disk: %s, %s' % (d.node, d.size_text),
                      'Candidates: %s' % ', '.join(d.sg_candidates),
                      'Control node: %s' % (d.control_node or 'none'),
                      'Status: %s' % (self.current.status.security_name if self.current.status else self.current.error),
                      'Cipher: %s' % (self.current.status.cipher_name if self.current.status else 'n/a'),
                      'Partitions: %s' % ', '.join('%s %s %s' % (p.node, p.fstype, p.mountpoint) for p in d.partitions)]
        lines.append('')
        lines.append('Recent activity:')
        lines += self.console.toPlainText().splitlines()[-25:]
        return '\n'.join(lines)

    def copy_diagnostics(self):
        text = self.diagnostics_text()
        self.diag_text.setPlainText(text)
        QApplication.clipboard().setText(text)
        self.append_log('Diagnostics copied to clipboard')

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, 'Please wait', 'An operation is still running. Wait for it to finish before closing.')
            event.ignore()
            return
        super().closeEvent(event)
