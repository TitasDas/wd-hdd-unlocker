#!/usr/bin/env python3
"""Command-line companion to the desktop app. Same engine, no Qt.

Examples:
  sudo ./wdctl.py status
  sudo ./wdctl.py unlock
  sudo ./wdctl.py lock
  sudo ./wdctl.py set-password --hint "pet name"
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wdpassport import APP_NAME, VERSION  # noqa: E402
from wdpassport.manager import DriveManager, OperationError  # noqa: E402


def pick(manager, disk):
    states = manager.scan()
    if not states:
        raise OperationError('No WD drive found.')
    if disk:
        for st in states:
            if st.drive.disk == disk or st.drive.node == disk:
                return st
        raise OperationError('No WD drive at %s. Found: %s' % (disk, ', '.join(s.drive.node for s in states)))
    if len(states) > 1:
        raise OperationError('Several WD drives found (%s). Pick one with --device.' % ', '.join(s.drive.node for s in states))
    return states[0]


def ask(prompt, confirm=False):
    value = getpass.getpass(prompt)
    if confirm and getpass.getpass('Repeat: ') != value:
        raise OperationError('Passwords do not match.')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(prog='wdctl', description='%s command line' % APP_NAME)
    parser.add_argument('--device', help='disk node to act on, e.g. /dev/sdb (only needed with several WD drives)')
    parser.add_argument('--quiet', action='store_true', help='hide the activity log')
    parser.add_argument('--version', action='version', version='%s %s' % (APP_NAME, VERSION))
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status', help='show security status and hint')
    sub.add_parser('unlock', help='unlock and mount')
    sub.add_parser('mount', help='mount an unlocked drive for the desktop user')
    sub.add_parser('lock', help='unmount, power off and relock')
    p = sub.add_parser('set-password', help='turn on password protection')
    p.add_argument('--hint', default='')
    p = sub.add_parser('change-password', help='change the password (drive must be unlocked)')
    p.add_argument('--hint', default=None)
    sub.add_parser('remove-password', help='turn off password protection (drive must be unlocked)')
    p = sub.add_parser('format', help='repartition and format an unlocked drive; deletes all files')
    p.add_argument('--fs', choices=['exfat', 'ntfs', 'ext4'], required=True)
    p.add_argument('--label', default='My Passport')
    p = sub.add_parser('erase', help='reset the encryption key; destroys all data')
    p.add_argument('--format', choices=['exfat', 'ntfs', 'ext4'], default=None)
    p.add_argument('--label', default='My Passport')
    args = parser.parse_args(argv)

    if os.geteuid() != 0:
        print('Run this with sudo.', file=sys.stderr)
        return 1

    log = (lambda m: None) if args.quiet else (lambda m: print('  ' + m, file=sys.stderr))
    manager = DriveManager(log=log)
    try:
        state = pick(manager, args.device)
        d = state.drive
        if args.cmd == 'status':
            print('Drive:     %s (%s, %s)' % (d.display_name, d.node, d.size_text))
            print('Serial:    %s' % d.masked_serial)
            if state.status:
                print('Security:  %s' % state.status.security_name)
                print('Cipher:    %s' % state.status.cipher_name)
                print('Hint:      %s' % (state.hint or '-'))
            else:
                print('Security:  not answering WD commands (%s)' % state.error)
            for part in d.partitions:
                print('Volume:    %s %s %s %s' % (part.node, part.fstype or '?', part.label, part.mountpoint or 'not mounted'))
        elif args.cmd == 'unlock':
            targets = manager.unlock(state, ask('Drive password: '))
            print('Mounted at: ' + ', '.join(targets))
        elif args.cmd == 'mount':
            print('Mounted at: ' + ', '.join(manager.mount(state)))
        elif args.cmd == 'lock':
            manager.eject_and_lock(state)
            print('Drive ejected and locked. Reconnect it to use it again.')
        elif args.cmd == 'set-password':
            manager.set_password(state, ask('New password: ', confirm=True), args.hint)
            print('Password set.')
        elif args.cmd == 'change-password':
            old = ask('Current password: ')
            new = ask('New password: ', confirm=True)
            manager.change_password(state, old, new, args.hint)
            print('Password changed.')
        elif args.cmd == 'remove-password':
            manager.remove_password(state, ask('Current password: '))
            print('Password removed.')
        elif args.cmd == 'format':
            print('This deletes every file on %s (%s). Type FORMAT to continue: ' % (d.display_name, d.node), end='', flush=True)
            if sys.stdin.readline().strip() != 'FORMAT':
                print('Cancelled.')
                return 1
            node = manager.format_drive(state, args.fs, args.label)
            print('Formatted %s as %s.' % (node, args.fs))
        elif args.cmd == 'erase':
            print('This destroys every file on %s (%s). Type ERASE to continue: ' % (d.display_name, d.node), end='', flush=True)
            if sys.stdin.readline().strip() != 'ERASE':
                print('Cancelled.')
                return 1
            manager.erase(state, args.format, args.label)
            print('Drive erased.')
    except OperationError as exc:
        print('Error: %s' % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
