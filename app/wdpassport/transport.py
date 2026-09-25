"""SCSI pass-through transports.

`SgIoTransport` talks to the kernel directly through the SG_IO ioctl, which is
what sg_raw does under the hood. `SgRawTransport` shells out to sg_raw and is
kept as a fallback for systems where the ioctl path misbehaves. Both expose the
same `execute` call so the rest of the app does not care which one is in use.
"""

import ctypes
import fcntl
import os
import re
import shutil
import subprocess
import tempfile

from . import protocol

SG_IO = 0x2285
SG_DXFER_NONE = -1
SG_DXFER_TO_DEV = -2
SG_DXFER_FROM_DEV = -3
SG_INFO_OK_MASK = 0x1
SG_INFO_CHECK = 0x1
DRIVER_SENSE = 0x08
SENSE_LEN = 32
DEFAULT_TIMEOUT_MS = 20000



class SgIoHdr(ctypes.Structure):
    """struct sg_io_hdr from <scsi/sg.h>, native layout (88 bytes on x86_64)."""
    _fields_ = [
        ('interface_id', ctypes.c_int),
        ('dxfer_direction', ctypes.c_int),
        ('cmd_len', ctypes.c_ubyte),
        ('mx_sb_len', ctypes.c_ubyte),
        ('iovec_count', ctypes.c_ushort),
        ('dxfer_len', ctypes.c_uint),
        ('dxferp', ctypes.c_void_p),
        ('cmdp', ctypes.c_void_p),
        ('sbp', ctypes.c_void_p),
        ('timeout', ctypes.c_uint),
        ('flags', ctypes.c_uint),
        ('pack_id', ctypes.c_int),
        ('usr_ptr', ctypes.c_void_p),
        ('status', ctypes.c_ubyte),
        ('masked_status', ctypes.c_ubyte),
        ('msg_status', ctypes.c_ubyte),
        ('sb_len_wr', ctypes.c_ubyte),
        ('host_status', ctypes.c_ushort),
        ('driver_status', ctypes.c_ushort),
        ('resid', ctypes.c_int),
        ('duration', ctypes.c_uint),
        ('info', ctypes.c_uint),
    ]


class ScsiError(Exception):
    """A command completed but the device reported a failure."""

    def __init__(self, message, sense=None, node=''):
        super().__init__(message)
        self.sense = sense
        self.node = node

    def __str__(self):
        base = super().__str__()
        return '%s [%s]' % (base, self.node) if self.node else base


class TransportUnavailable(Exception):
    """The transport cannot be used on this device node."""


class SgIoTransport:
    name = 'SG_IO'

    def __init__(self, timeout_ms=DEFAULT_TIMEOUT_MS):
        self.timeout_ms = timeout_ms

    def execute(self, node, cdb, data_out=None, data_in_len=0):
        """Run one command. Returns bytes read (possibly empty).

        Raises ScsiError on CHECK CONDITION, TransportUnavailable when the node
        does not accept SG_IO at all, OSError for anything else.
        """
        cdb = bytes(cdb)
        if data_out is not None and data_in_len:
            raise ValueError('bidirectional transfers are not supported')

        cmd_buf = ctypes.create_string_buffer(cdb, len(cdb))
        sense_buf = ctypes.create_string_buffer(SENSE_LEN)
        if data_out is not None:
            direction = SG_DXFER_TO_DEV
            data_buf = ctypes.create_string_buffer(bytes(data_out), len(data_out))
            dxfer_len = len(data_out)
        elif data_in_len:
            direction = SG_DXFER_FROM_DEV
            data_buf = ctypes.create_string_buffer(data_in_len)
            dxfer_len = data_in_len
        else:
            direction = SG_DXFER_NONE
            data_buf = ctypes.create_string_buffer(1)
            dxfer_len = 0

        hdr = SgIoHdr()
        hdr.interface_id = ord('S')
        hdr.dxfer_direction = direction
        hdr.cmd_len = len(cdb)
        hdr.mx_sb_len = SENSE_LEN
        hdr.dxfer_len = dxfer_len
        hdr.dxferp = ctypes.addressof(data_buf) if dxfer_len else None
        hdr.cmdp = ctypes.addressof(cmd_buf)
        hdr.sbp = ctypes.addressof(sense_buf)
        hdr.timeout = self.timeout_ms

        try:
            fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        except OSError as exc:
            raise TransportUnavailable('cannot open %s: %s' % (node, exc.strerror))
        try:
            try:
                fcntl.ioctl(fd, SG_IO, hdr, True)
            except OSError as exc:
                if exc.errno in (25, 22, 95):  # ENOTTY, EINVAL, EOPNOTSUPP
                    raise TransportUnavailable('%s does not accept SG_IO: %s' % (node, exc.strerror))
                raise
        finally:
            os.close(fd)

        status = hdr.status
        sb_len_wr = hdr.sb_len_wr
        host_status = hdr.host_status
        driver_status = hdr.driver_status
        resid = hdr.resid

        sense = None
        if sb_len_wr:
            sense = protocol.parse_sense(sense_buf.raw[:sb_len_wr])

        driver_code = driver_status & 0x0F
        failed = status != 0 or host_status != 0 or driver_code not in (0, DRIVER_SENSE)
        if failed:
            if sense is not None:
                raise ScsiError(protocol.describe_sense(sense), sense=sense, node=node)
            raise ScsiError(
                'command failed (scsi status 0x%02x, host 0x%02x, driver 0x%02x)' % (status, host_status, driver_status),
                node=node)

        if dxfer_len and direction == SG_DXFER_FROM_DEV:
            got = max(0, dxfer_len - max(0, resid))
            return data_buf.raw[:got]
        return b''


class SgRawTransport:
    name = 'sg_raw'

    _SENSE_RE = re.compile(r'Sense key:\s*([A-Za-z ]+?)\s+ASC=([0-9a-fA-F]+),\s*ASCQ=([0-9a-fA-F]+)')
    _KEY_NAMES = {v.lower(): k for k, v in protocol.SENSE_KEY_NAMES.items()}

    def __init__(self, binary=None, timeout_s=30):
        self.binary = binary or shutil.which('sg_raw')
        self.timeout_s = timeout_s

    def available(self):
        return bool(self.binary)

    def execute(self, node, cdb, data_out=None, data_in_len=0):
        if not self.binary:
            raise TransportUnavailable('sg_raw is not installed')
        args = [self.binary]
        in_path = out_path = None
        try:
            if data_out is not None:
                fd, in_path = tempfile.mkstemp(prefix='wdsec_')
                os.close(fd)
                os.chmod(in_path, 0o600)
                with open(in_path, 'wb') as fh:
                    fh.write(bytes(data_out))
                args += ['-s', str(len(data_out)), '-i', in_path]
            if data_in_len:
                fd, out_path = tempfile.mkstemp(prefix='wdsec_')
                os.close(fd)
                os.chmod(out_path, 0o600)
                args += ['-r', str(data_in_len), '-o', out_path]
            args.append(node)
            args += ['%02x' % b for b in bytes(cdb)]
            proc = subprocess.run(args, capture_output=True, text=True, timeout=self.timeout_s)
            if proc.returncode != 0:
                text = ((proc.stderr or '') + ' ' + (proc.stdout or '')).strip()
                sense = self._sense_from_text(text)
                if sense is not None:
                    raise ScsiError(protocol.describe_sense(sense), sense=sense, node=node)
                if 'No such device' in text or 'Permission denied' in text or 'cannot open' in text.lower():
                    raise TransportUnavailable(text)
                raise ScsiError(text.replace('\n', ' ') or ('sg_raw exit code %d' % proc.returncode), node=node)
            if out_path:
                with open(out_path, 'rb') as fh:
                    return fh.read()
            return b''
        finally:
            for path in (in_path, out_path):
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    def _sense_from_text(self, text):
        m = self._SENSE_RE.search(text)
        if not m:
            return None
        key = self._KEY_NAMES.get(m.group(1).strip().lower())
        if key is None:
            return None
        return protocol.SenseInfo(key, int(m.group(2), 16), int(m.group(3), 16))


class ChainedTransport:
    """Try SG_IO first and fall back to sg_raw when the ioctl path is unusable."""

    name = 'auto'

    def __init__(self, transports=None):
        self.transports = transports or [SgIoTransport(), SgRawTransport()]
        self.last_used = None

    def execute(self, node, cdb, data_out=None, data_in_len=0):
        last_exc = None
        for transport in self.transports:
            if isinstance(transport, SgRawTransport) and not transport.available():
                continue
            try:
                result = transport.execute(node, cdb, data_out=data_out, data_in_len=data_in_len)
                self.last_used = transport.name
                return result
            except TransportUnavailable as exc:
                last_exc = exc
                continue
        raise TransportUnavailable(str(last_exc) if last_exc else 'no SCSI transport available')
