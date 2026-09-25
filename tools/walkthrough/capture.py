"""Drive the real app (demo mode, offscreen) and capture the states the video needs."""
import os, sys, time
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app'))
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import Qt
from wdpassport import protocol
from wdpassport.manager import DriveManager
from wdpassport.simulator import SimulatedSystem, SimulatedTransport
from wdpassport.ui.main_window import MainWindow
from wdpassport.ui import dialogs

OUT = 'caps'
app = QApplication([])
transport = SimulatedTransport(security=protocol.STATUS_LOCKED, password='demo-pass', hint='First pet, lower case')
system = SimulatedSystem(transport)
system.parts[0].label = 'Passport'
system.parts[0].size = 2 * 10 ** 12
manager = DriveManager(transport=transport, system=system)
w = MainWindow(manager, demo=True)
w.resize(1080, 780)
w.show()

def settle():
    t = time.time() + 10
    while time.time() < t:
        app.processEvents()
        if not w.busy:
            app.processEvents(); return
        time.sleep(0.01)

def grab(name, dialog=None):
    app.processEvents()
    w.grab().save(f'{OUT}/{name}.png')
    if dialog is not None:
        dialog.grab().save(f'{OUT}/{name}-dialog.png')

settle()
w.show_page('drive'); grab('01-drive-locked')
w.show_page('unlock'); grab('02-unlock-empty')
pw = 'demo-pass'
for i in range(1, len(pw) + 1):
    w.unlock_pw.edit.setText(pw[:i]); grab('03-typing-%02d' % i)
w.do_unlock(); settle()
w.show_page('drive'); grab('04-drive-unlocked')
w.table.selectRow(0); grab('05-volumes')
w.show_page('security'); grab('06-password')
d = dialogs.ChangePasswordDialog('WD My Passport 25E1', 'First pet, lower case', w)
d.old.edit.setText('demo-pass'); d.new.edit.setText('new-secret-2026'); d.confirm.edit.setText('new-secret-2026'); d.hint.setText('Second pet, lower case')
d.show(); app.processEvents(); grab('07-change-dialog', d); d.close()
w.show_page('advanced'); grab('08-advanced')
f = dialogs.FormatDialog('WD My Passport 25E1', [('exfat', 'exFAT (Windows, macOS and Linux)'), ('ntfs', 'NTFS (Windows and Linux)'), ('ext4', 'ext4 (Linux only)')], 'Passport', w)
f.label_edit.setText('Backups'); f.typed.setText('FORMAT'); f.show(); app.processEvents(); grab('09-format-dialog', f); f.close()
e = dialogs.EraseDialog('WD My Passport 25E1', 'WX1…5678', [('exfat', 'exFAT (Windows, macOS and Linux)')], w)
e.typed.setText('ERASE'); e.show(); app.processEvents(); grab('10-erase-dialog', e); e.close()
w.show_page('activity'); grab('11-activity')
w.show_page('drive'); w.apply_theme('dark'); grab('12-drive-dark')
w.apply_theme('light')
# eject: simulate the confirm by calling the manager directly, then render the empty state
manager.eject_and_lock(w.current); w.refresh(); settle(); grab('13-ejected')
print('captured', sorted(os.listdir(OUT)))
