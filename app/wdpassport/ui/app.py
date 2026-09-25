"""Application entry point: argument parsing, privilege checks, window setup."""

import argparse
import os
import sys

from .. import APP_ID, APP_NAME, VERSION
from ..devices import which
from ..manager import DriveManager

REQUIRED_TOOLS = ['lsblk', 'findmnt', 'mount', 'umount', 'udevadm', 'partprobe', 'lsusb']


def parse_args(argv):
    parser = argparse.ArgumentParser(prog=APP_ID, description=APP_NAME)
    parser.add_argument('--demo', action='store_true', help='run against a simulated drive (no root, no hardware)')
    parser.add_argument('--theme', choices=['light', 'dark'], default=None, help='start in this theme')
    parser.add_argument('--screenshots', metavar='DIR', help='with --demo: render every page in both themes to DIR and exit')
    parser.add_argument('--version', action='version', version='%s %s' % (APP_NAME, VERSION))
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if not args.demo:
        if os.geteuid() != 0:
            print('This program needs root privileges to talk to the drive. Run it with pkexec or sudo, '
                  'or use --demo to preview the interface.', file=sys.stderr)
            return 1
        missing = [t for t in REQUIRED_TOOLS if not which(t)]
        if missing:
            print('Missing required system tools: %s' % ', '.join(missing), file=sys.stderr)
            print('Install the util-linux, udev, parted and usbutils packages and retry.', file=sys.stderr)
            return 1

    os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')
    from PyQt5.QtCore import QByteArray, Qt
    from PyQt5.QtGui import QIcon, QPixmap
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtGui import QPainter
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)

    from .icons import app_icon_svg
    renderer = QSvgRenderer(QByteArray(app_icon_svg().encode('utf-8')))
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    app.setWindowIcon(QIcon(pm))

    if args.demo:
        from .. import protocol
        from ..simulator import SimulatedSystem, SimulatedTransport
        transport = SimulatedTransport(security=protocol.STATUS_LOCKED, password='demo-pass', hint='Demo drive: the password is demo-pass')
        manager = DriveManager(transport=transport, system=SimulatedSystem(transport))
    else:
        manager = DriveManager()

    from .main_window import MainWindow
    window = MainWindow(manager, demo=args.demo)
    if args.theme:
        window.apply_theme(args.theme)
    window.show_page('drive')
    window.show()
    if args.demo and args.screenshots:
        _schedule_screenshots(app, window, args.screenshots)
    return app.exec_()


def _schedule_screenshots(app, window, out_dir):
    """Walk every page in both themes, save a PNG of each, then quit."""
    from PyQt5.QtCore import QTimer
    os.makedirs(out_dir, exist_ok=True)
    steps = [('light', 'unlock', 'locked'), ('dark', 'unlock', 'locked'), ('light', 'drive', 'locked'), ('unlock', None, None)]
    for theme_name in ('light', 'dark'):
        for key in ('drive', 'unlock', 'security', 'advanced', 'activity'):
            steps.append((theme_name, key, ''))
    state = {'i': 0}

    def step():
        if window.busy:
            QTimer.singleShot(200, step)
            return
        if state['i'] >= len(steps):
            app.quit()
            return
        theme_name, key, suffix = steps[state['i']]
        state['i'] += 1
        if theme_name == 'unlock':
            window.unlock_pw.edit.setText('demo-pass')
            window.do_unlock()
            QTimer.singleShot(400, step)
            return
        if theme_name != window.theme_name:
            window.apply_theme(theme_name)
        window.show_page(key)
        app.processEvents()
        name = 'screenshot-%s-%s%s.png' % (theme_name, key, ('-' + suffix) if suffix else '')
        QTimer.singleShot(150, lambda: _grab(window, os.path.join(out_dir, name), step))

    QTimer.singleShot(600, step)


def _grab(window, path, then):
    window.grab().save(path)
    then()
