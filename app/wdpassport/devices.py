"""Device discovery and Linux plumbing: sysfs, udev, lsblk, mounts.

Everything here shells out to standard tools or reads /sys, and every call is
funnelled through `run_cmd` so tests can replace it.
"""

import json
import os
import pwd
import re
import shutil
import subprocess
import time

WD_USB_VENDOR = '1058'
SG_TYPE_ENCLOSURE = '13'
DISK_BY_ID = '/dev/disk/by-id'
SYS_SG = '/sys/class/scsi_generic'
SYS_BLOCK = '/sys/block'


def run_cmd(args, check=False, timeout=60, input_text=None):
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=input_text)
    except FileNotFoundError:
        return '', '%s: command not found' % args[0], 127
    except subprocess.TimeoutExpired:
        return '', '%s: timed out after %ss' % (args[0], timeout), 124
    out = (proc.stdout or '').strip()
    err = (proc.stderr or '').strip()
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, args, output=out + err)
    return out, err, proc.returncode


_EXTRA_PATH = '/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin'


def which(binary):
    """shutil.which that also looks in the sbin directories root tools live in."""
    path = os.environ.get('PATH', '') + ':' + _EXTRA_PATH
    return shutil.which(binary, path=path) is not None


def read_sys(path, default=''):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read().strip()
    except OSError:
        return default


def write_sys(path, value):
    with open(path, 'w') as fh:
        fh.write(value)


def udev_properties(devnode):
    out, _, rc = run_cmd(['udevadm', 'info', '--query=property', '--name', devnode])
    props = {}
    if rc != 0:
        return props
    for line in out.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            props[key.strip()] = value.strip()
    return props


def normalize_id_path(id_path):
    if not id_path:
        return ''
    return id_path.split('-scsi-', 1)[0] if '-scsi-' in id_path else id_path


class Partition:
    __slots__ = ('name', 'fstype', 'label', 'size', 'mountpoint', 'uuid')

    def __init__(self, name, fstype='', label='', size=0, mountpoint='', uuid=''):
        self.name = name
        self.fstype = fstype or ''
        self.label = label or ''
        self.size = size or 0
        self.mountpoint = mountpoint or ''
        self.uuid = uuid or ''

    @property
    def node(self):
        return '/dev/' + self.name


class Drive:
    """A WD USB disk as seen by the kernel."""

    def __init__(self, disk):
        self.disk = disk                 # e.g. 'sdb'
        self.model = ''
        self.vendor = ''
        self.serial = ''
        self.usb_id = ''
        self.id_path = ''
        self.size = 0
        self.partitions = []
        self.control_node = ''          # node that answered WD security commands
        self.sg_candidates = []

    @property
    def node(self):
        return '/dev/' + self.disk

    @property
    def display_name(self):
        model = self.model.replace('_', ' ').strip() or 'WD drive'
        vendor = self.vendor.replace('_', ' ').strip()
        if vendor and vendor.lower() not in model.lower():
            return '%s %s' % (vendor, model)
        return model

    @property
    def size_text(self):
        return human_size(self.size)

    @property
    def masked_serial(self):
        s = self.serial
        if len(s) <= 6:
            return s
        return s[:3] + '…' + s[-4:]

    @property
    def mounted_partitions(self):
        return [p for p in self.partitions if p.mountpoint]

    def __repr__(self):
        return 'Drive(%s, %s, %s)' % (self.disk, self.model, self.size_text)


def human_size(n):
    if not n:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    value = float(n)
    for unit in units:
        if value < 1000 or unit == units[-1]:
            return ('%.1f %s' % (value, unit)) if unit not in ('B',) else ('%d %s' % (value, unit))
        value /= 1000.0
    return '%d B' % n


def wd_usb_present():
    out, _, _ = run_cmd(['lsusb'])
    return [line for line in out.splitlines() if ('ID %s:' % WD_USB_VENDOR) in line or 'western digital' in line.lower()]


def find_wd_disks():
    """Return sorted disk names (sdX) that /dev/disk/by-id attributes to a WD USB device."""
    if not os.path.isdir(DISK_BY_ID):
        return []
    disks = set()
    for entry in os.listdir(DISK_BY_ID):
        if not entry.lower().startswith('usb-wd'):
            continue
        full = os.path.join(DISK_BY_ID, entry)
        if not os.path.islink(full):
            continue
        base = os.path.basename(os.path.realpath(full))
        if re.match(r'^sd[a-z]+$', base):
            disks.add(base)
    return sorted(disks)


def list_partitions(disk):
    out, _, rc = run_cmd(['lsblk', '-J', '-b', '-o', 'NAME,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINT,UUID', '/dev/' + disk])
    parts = []
    if rc != 0 or not out:
        return parts
    try:
        tree = json.loads(out)
    except ValueError:
        return parts

    def walk(nodes):
        for node in nodes or []:
            if node.get('type') == 'part':
                parts.append(Partition(
                    node.get('name', ''), node.get('fstype'), node.get('label'),
                    int(node.get('size') or 0), node.get('mountpoint'), node.get('uuid')))
            walk(node.get('children'))

    walk(tree.get('blockdevices'))
    return parts


def describe_drive(disk):
    drive = Drive(disk)
    props = udev_properties(drive.node)
    drive.model = props.get('ID_MODEL', '') or read_sys(os.path.join(SYS_BLOCK, disk, 'device', 'model'))
    drive.vendor = props.get('ID_VENDOR', '') or read_sys(os.path.join(SYS_BLOCK, disk, 'device', 'vendor'))
    drive.serial = props.get('ID_SERIAL_SHORT', '') or props.get('ID_SERIAL', '')
    vid = props.get('ID_VENDOR_ID', '')
    pid = props.get('ID_MODEL_ID', '')
    drive.usb_id = ('%s:%s' % (vid, pid)) if vid and pid else ''
    drive.id_path = normalize_id_path(props.get('ID_PATH', ''))
    sectors = read_sys(os.path.join(SYS_BLOCK, disk, 'size'), '0')
    try:
        drive.size = int(sectors) * 512
    except ValueError:
        drive.size = 0
    drive.partitions = list_partitions(disk)
    drive.sg_candidates = control_node_candidates(drive)
    return drive


def find_sg_devices(scsi_type=SG_TYPE_ENCLOSURE):
    if not os.path.isdir(SYS_SG):
        return []
    found = []
    for sg in sorted(os.listdir(SYS_SG), key=_natural_key):
        if not re.match(r'^sg\d+$', sg):
            continue
        if read_sys(os.path.join(SYS_SG, sg, 'device', 'type')) == scsi_type:
            found.append(sg)
    return found


def _natural_key(name):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', name)]


def sg_for_disk(disk):
    sg_dir = os.path.join(SYS_BLOCK, disk, 'device', 'scsi_generic')
    if os.path.isdir(sg_dir):
        sgs = sorted([n for n in os.listdir(sg_dir) if re.match(r'^sg\d+$', n)], key=_natural_key)
        if sgs:
            return sgs[0]
    if os.path.isdir(SYS_SG):
        for sg in sorted(os.listdir(SYS_SG), key=_natural_key):
            block_dir = os.path.join(SYS_SG, sg, 'device', 'block')
            if os.path.isdir(block_dir) and disk in os.listdir(block_dir):
                return sg
    return None


def control_node_candidates(drive):
    """Nodes to try for WD vendor commands, most likely first.

    The enclosure-services node (SCSI type 13) on the same USB path answers on
    most bridges. Some bridges only take vendor commands on the disk node.
    """
    candidates = []
    if drive.id_path:
        for sg in find_sg_devices():
            sg_path = normalize_id_path(udev_properties('/dev/' + sg).get('ID_PATH', ''))
            if sg_path and sg_path == drive.id_path:
                candidates.append('/dev/' + sg)
    mapped = sg_for_disk(drive.disk)
    if mapped and '/dev/' + mapped not in candidates:
        candidates.append('/dev/' + mapped)
    if not candidates:
        for sg in find_sg_devices():
            candidates.append('/dev/' + sg)
    if drive.node not in candidates:
        candidates.append(drive.node)
    return candidates


# --- desktop user -------------------------------------------------------------

class DesktopUser:
    __slots__ = ('name', 'uid', 'gid', 'home')

    def __init__(self, name, uid, gid, home):
        self.name = name
        self.uid = uid
        self.gid = gid
        self.home = home


def desktop_user():
    """The unprivileged user who launched the app via pkexec or sudo, if any."""
    uid = None
    for var in ('PKEXEC_UID', 'SUDO_UID'):
        value = os.environ.get(var)
        if value and value.isdigit():
            uid = int(value)
            break
    if uid is None:
        name = os.environ.get('SUDO_USER')
        if name:
            try:
                uid = pwd.getpwnam(name).pw_uid
            except KeyError:
                uid = None
    if uid is None or uid == 0:
        return None
    try:
        entry = pwd.getpwuid(uid)
    except KeyError:
        return None
    return DesktopUser(entry.pw_name, entry.pw_uid, entry.pw_gid, entry.pw_dir)


# --- mounting -----------------------------------------------------------------

USER_MAPPED_FS = {'ntfs', 'ntfs3', 'exfat', 'vfat', 'msdos', 'hfsplus', 'udf'}
POSIX_FS = {'ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'f2fs'}


def mount_options(fstype, user):
    """Mount options that give the desktop user ownership of the files."""
    fstype = (fstype or '').lower()
    opts = ['nosuid', 'nodev']
    if user and fstype in USER_MAPPED_FS:
        opts += ['uid=%d' % user.uid, 'gid=%d' % user.gid]
        if fstype in ('vfat', 'msdos', 'exfat', 'ntfs', 'ntfs3', 'hfsplus'):
            opts.append('umask=022')
        if fstype in ('vfat', 'msdos'):
            opts += ['utf8', 'shortname=mixed']
        if fstype in ('ntfs', 'ntfs3'):
            opts.append('windows_names')
    return opts


def safe_mount_name(text, fallback='wd-drive'):
    cleaned = re.sub(r'[^A-Za-z0-9._ -]+', '', text or '').strip().strip('.')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned or fallback


def choose_mount_dir(name, user):
    """Pick a mount point the desktop sees as a normal removable volume."""
    if user:
        media_user = os.path.join('/media', user.name)
        if os.path.isdir(media_user):
            return unique_dir(os.path.join(media_user, name))
        run_media = os.path.join('/run/media', user.name)
        if os.path.isdir(run_media):
            return unique_dir(os.path.join(run_media, name))
    return unique_dir(os.path.join('/mnt', name))


def unique_dir(path):
    """Return path, or path with a numeric suffix if it exists and is in use."""
    candidate = path
    n = 1
    while os.path.exists(candidate):
        if os.path.isdir(candidate) and not os.listdir(candidate) and not is_mountpoint(candidate):
            return candidate
        n += 1
        candidate = '%s-%d' % (path, n)
    return candidate


def is_mountpoint(path):
    _, _, rc = run_cmd(['findmnt', '-n', '-M', path])
    return rc == 0


def mount_target(devnode):
    out, _, rc = run_cmd(['findmnt', '-n', '-o', 'TARGET', '--source', devnode])
    target = out.splitlines()[0].strip() if rc == 0 and out.strip() else ''
    return target if target and os.path.isdir(target) else ''


def mount_partition(part, user, log):
    """Mount a partition for the desktop user. Returns the mount point."""
    fstype = (part.fstype or '').lower()
    name = safe_mount_name(part.label) if part.label else safe_mount_name(part.name)
    target = choose_mount_dir(name, user)
    os.makedirs(target, exist_ok=True)
    opts = mount_options(fstype, user)
    args = ['mount']
    if fstype in ('ntfs', 'ntfs3'):
        # Prefer ntfs-3g when present; it is the mature driver on most distros.
        if which('mount.ntfs-3g') or which('ntfs-3g'):
            args += ['-t', 'ntfs-3g']
        elif os.path.isdir('/sys/module/ntfs3') or _modprobe('ntfs3'):
            args += ['-t', 'ntfs3']
            opts = [o for o in opts if o != 'windows_names']
    if opts:
        args += ['-o', ','.join(opts)]
    args += [part.node, target]
    log('Mounting %s as %s' % (part.node, target))
    _, err, rc = run_cmd(args)
    if rc == 0:
        return target
    if opts and fstype in USER_MAPPED_FS:
        # Retry without driver-specific niceties in case the driver is picky.
        basic = [o for o in opts if o.startswith(('uid=', 'gid=', 'umask='))]
        log('Mount with full options failed (%s). Retrying with basic ownership options.' % (err or 'no detail'))
        _, err, rc = run_cmd(['mount', '-o', ','.join(basic), part.node, target])
        if rc == 0:
            return target
    try:
        os.rmdir(target)
    except OSError:
        pass
    raise RuntimeError('mount failed for %s: %s' % (part.node, err or 'unknown error'))


def _modprobe(module):
    _, _, rc = run_cmd(['modprobe', module])
    return rc == 0


def unmount(target_or_node, log):
    run_cmd(['sync'])
    _, err, rc = run_cmd(['umount', target_or_node])
    if rc == 0:
        return True
    log('umount failed (%s); trying udisks' % (err or 'no detail'))
    _, err2, rc2 = run_cmd(['udisksctl', 'unmount', '-b', target_or_node, '--no-user-interaction'])
    if rc2 == 0:
        return True
    raise RuntimeError('could not unmount %s: %s' % (target_or_node, err2 or err))


def user_can_write(path, user):
    """Whether the desktop user can create files in path (root bypasses checks, so test as them)."""
    if user is None:
        return os.access(path, os.W_OK)
    if which('sudo'):
        _, err, rc = run_cmd(['sudo', '-n', '-u', '#%d' % user.uid, 'test', '-w', path])
        if rc == 0:
            return True
        if rc == 1 and not err:
            return False
    try:
        st = os.stat(path)
    except OSError:
        return False
    if st.st_uid == user.uid:
        return bool(st.st_mode & 0o200)
    if st.st_gid == user.gid:
        return bool(st.st_mode & 0o020)
    return bool(st.st_mode & 0o002)


def usb_device_dir(disk):
    """The /sys/bus/usb/devices/... directory of the USB device behind a disk."""
    path = os.path.realpath(os.path.join(SYS_BLOCK, disk))
    while path and path != '/':
        if os.path.exists(os.path.join(path, 'idVendor')):
            return path
        path = os.path.dirname(path)
    return ''


def power_off(drive, log):
    """Safely stop and power down the USB device. The drive relocks when power drops."""
    run_cmd(['sync'])
    _, err, rc = run_cmd(['udisksctl', 'power-off', '-b', drive.node, '--no-user-interaction'], timeout=90)
    if rc == 0:
        return 'udisks'
    log('udisks power-off unavailable (%s); using sysfs' % (err or 'no detail'))
    usb_dir = usb_device_dir(drive.disk)
    delete = os.path.join(SYS_BLOCK, drive.disk, 'device', 'delete')
    if os.path.exists(delete):
        try:
            write_sys(delete, '1')
        except OSError as exc:
            log('Could not detach SCSI device: %s' % exc)
    if usb_dir and os.path.exists(os.path.join(usb_dir, 'remove')):
        write_sys(os.path.join(usb_dir, 'remove'), '1')
        return 'sysfs'
    raise RuntimeError('no way to power off %s on this system' % drive.node)


def rescan_disk(disk, log, wait_s=12):
    """Make the kernel re-read a drive that just changed from locked to unlocked."""
    run_cmd(['partprobe', '/dev/' + disk])
    if list_partitions(disk):
        return disk
    run_cmd(['blockdev', '--rereadpt', '/dev/' + disk])
    if list_partitions(disk):
        return disk
    # Some bridges report zero capacity while locked; a SCSI rescan fixes that.
    dev_dir = os.path.realpath(os.path.join(SYS_BLOCK, disk, 'device'))
    host = None
    for part in dev_dir.split('/'):
        if re.match(r'^host\d+$', part):
            host = part
    if not host:
        return disk
    log('Re-scanning SCSI %s so the kernel picks up the unlocked capacity' % host)
    try:
        write_sys(os.path.join(dev_dir, 'delete'), '1')
        time.sleep(1.0)
        write_sys(os.path.join('/sys/class/scsi_host', host, 'scan'), '- - -')
    except OSError as exc:
        log('SCSI rescan failed: %s' % exc)
        return disk
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(0.5)
        disks = find_wd_disks()
        if disks:
            new = disk if disk in disks else disks[0]
            run_cmd(['partprobe', '/dev/' + new])
            if list_partitions(new):
                return new
    return disk


def wait_for_automount(disk, wait_s=4.0):
    """Give the desktop's own automounter a moment; return partitions if it mounted any."""
    deadline = time.time() + wait_s
    while True:
        parts = list_partitions(disk)
        mounted = [p for p in parts if p.mountpoint]
        if mounted or time.time() >= deadline:
            return parts
        time.sleep(0.5)


def open_folder(path, user, log):
    if not path or not os.path.isdir(path):
        return False
    attempts = []
    if user and which('sudo'):
        env_prefix = ['sudo', '-n', '-u', '#%d' % user.uid, 'env',
                      'DISPLAY=%s' % os.environ.get('DISPLAY', ''),
                      'XAUTHORITY=%s' % os.environ.get('XAUTHORITY', ''),
                      'WAYLAND_DISPLAY=%s' % os.environ.get('WAYLAND_DISPLAY', ''),
                      'XDG_RUNTIME_DIR=/run/user/%d' % user.uid,
                      'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%d/bus' % user.uid]
        attempts.append(env_prefix + ['xdg-open', path])
        attempts.append(env_prefix + ['gio', 'open', path])
    attempts.append(['xdg-open', path])
    attempts.append(['gio', 'open', path])
    for cmd in attempts:
        tool = cmd[0] if cmd[0] != 'sudo' else 'xdg-open'
        if not which(tool):
            continue
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            log('Opened %s in the file manager' % path)
            return True
        except OSError:
            continue
    log('Could not open a file manager. Browse to %s manually.' % path)
    return False


def format_partition_table(disk, fstype, label, log):
    """Create one partition spanning the disk and format it. Destroys everything."""
    node = '/dev/' + disk
    tools = {'exfat': 'mkfs.exfat', 'ntfs': 'mkfs.ntfs', 'ext4': 'mkfs.ext4'}
    tool = tools.get(fstype)
    if not tool:
        raise RuntimeError('unsupported filesystem %r' % fstype)
    if not which(tool):
        raise RuntimeError('%s is not installed' % tool)
    if not which('parted'):
        raise RuntimeError('parted is not installed')
    log('Writing a new GPT partition table on %s' % node)
    run_cmd(['wipefs', '-a', node])
    _, err, rc = run_cmd(['parted', '-s', node, 'mklabel', 'gpt', 'mkpart', 'primary', '1MiB', '100%'], timeout=120)
    if rc != 0:
        raise RuntimeError('parted failed: %s' % err)
    run_cmd(['partprobe', node])
    deadline = time.time() + 10
    part = None
    while time.time() < deadline and not part:
        parts = list_partitions(disk)
        part = parts[0] if parts else None
        if not part:
            time.sleep(0.5)
    if not part:
        raise RuntimeError('the new partition did not appear')
    safe_label = safe_mount_name(label, 'WD Drive')[:11 if fstype == 'exfat' else 32]
    if fstype == 'exfat':
        cmd = [tool, '-n', safe_label, part.node]
    elif fstype == 'ntfs':
        cmd = [tool, '-Q', '-L', safe_label, part.node]
    else:
        cmd = [tool, '-q', '-F', '-L', safe_label, part.node]
    log('Formatting %s as %s' % (part.node, fstype))
    _, err, rc = run_cmd(cmd, timeout=600)
    if rc != 0:
        raise RuntimeError('%s failed: %s' % (tool, err))
    run_cmd(['partprobe', node])
    return part.node
