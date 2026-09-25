"""Pure functions for the WD My Passport vendor SCSI protocol.

Nothing in this module touches hardware. It builds command blocks, parses
responses and derives password blobs, so it can be unit tested exhaustively.

The command formats follow the community reference manual shipped with
KenMacD/wdpassport-utils (WD_Encryption_API.txt) and were cross-checked against
two independent implementations (wdutils.c and 0-duke/wdpassport-utils).
"""

import os
import struct
from hashlib import sha256

# Security status values returned by ENCRYPTION STATUS.
STATUS_NOT_PROTECTED = 0x00   # key scrambled with the vendor default password
STATUS_LOCKED = 0x01
STATUS_UNLOCKED = 0x02
STATUS_LOCKED_BLOCKED = 0x06  # too many failed attempts, power cycle needed
STATUS_NO_KEY = 0x07

STATUS_NAMES = {
    STATUS_NOT_PROTECTED: 'No password set',
    STATUS_LOCKED: 'Locked',
    STATUS_UNLOCKED: 'Unlocked',
    STATUS_LOCKED_BLOCKED: 'Locked (unlock attempts blocked)',
    STATUS_NO_KEY: 'No encryption key',
}

CIPHER_NAMES = {
    0x00: 'No encryption',
    0x10: 'AES-128 ECB',
    0x12: 'AES-128 CBC',
    0x18: 'AES-128 XTS',
    0x20: 'AES-256 ECB',
    0x22: 'AES-256 CBC',
    0x28: 'AES-256 XTS',
    0x30: 'Full disk encryption',
}

AES128_CIPHERS = (0x10, 0x12, 0x18)
AES256_CIPHERS = (0x20, 0x22, 0x28)
FDE_CIPHER = 0x30

DEFAULT_SALT = 'WDC.'
DEFAULT_ITERATIONS = 1000
HANDY_BLOCK_SIZE = 512
SECURITY_BLOCK = 1
USER_BLOCK = 2
SECURITY_BLOCK_SIGNATURE = b'\x00\x01DW'
USER_BLOCK_SIGNATURE = b'\x00\x02DW'
HINT_MAX_CHARS = 101
SALT_MAX_CHARS = 4
LABEL_MAX_CHARS = 32

STATUS_ALLOC_LEN = 0x30


class ProtocolError(Exception):
    """Raised when a response does not look like a WD security response."""


class EncryptionStatus:
    __slots__ = ('security', 'cipher', 'password_length', 'key_reset_enabler', 'ciphers')

    def __init__(self, security, cipher, password_length, key_reset_enabler, ciphers):
        self.security = security
        self.cipher = cipher
        self.password_length = password_length
        self.key_reset_enabler = key_reset_enabler
        self.ciphers = ciphers

    @property
    def security_name(self):
        return STATUS_NAMES.get(self.security, 'Unknown (0x%02x)' % self.security)

    @property
    def cipher_name(self):
        return CIPHER_NAMES.get(self.cipher, 'Unknown (0x%02x)' % self.cipher)

    @property
    def is_locked(self):
        return self.security in (STATUS_LOCKED, STATUS_LOCKED_BLOCKED)

    @property
    def is_unlocked(self):
        return self.security == STATUS_UNLOCKED

    @property
    def has_password(self):
        return self.security in (STATUS_LOCKED, STATUS_UNLOCKED, STATUS_LOCKED_BLOCKED)

    @property
    def is_accessible(self):
        return self.security in (STATUS_NOT_PROTECTED, STATUS_UNLOCKED)

    def __repr__(self):
        return 'EncryptionStatus(security=0x%02x, cipher=0x%02x, pwlen=%d)' % (
            self.security, self.cipher, self.password_length)


class SecurityBlock:
    """Handy store block 1: hashing parameters and the password hint."""

    __slots__ = ('iterations', 'salt', 'hint')

    def __init__(self, iterations=DEFAULT_ITERATIONS, salt=DEFAULT_SALT, hint=''):
        self.iterations = iterations
        self.salt = salt
        self.hint = hint

    def __eq__(self, other):
        return (isinstance(other, SecurityBlock)
                and (self.iterations, self.salt, self.hint)
                == (other.iterations, other.salt, other.hint))

    def __repr__(self):
        return 'SecurityBlock(iterations=%d, salt=%r, hint=%r)' % (self.iterations, self.salt, self.hint)


# --- command descriptor blocks -------------------------------------------------

def cdb_encryption_status(alloc_len=STATUS_ALLOC_LEN):
    return bytes([0xC0, 0x45, 0, 0, 0, 0, 0, (alloc_len >> 8) & 0xFF, alloc_len & 0xFF, 0])


def cdb_unlock(param_len):
    return bytes([0xC1, 0xE1, 0, 0, 0, 0, 0, (param_len >> 8) & 0xFF, param_len & 0xFF, 0])


def cdb_change_password(param_len):
    return bytes([0xC1, 0xE2, 0, 0, 0, 0, 0, (param_len >> 8) & 0xFF, param_len & 0xFF, 0])


def cdb_reset_key(key_reset_enabler, param_len):
    if len(key_reset_enabler) != 4:
        raise ValueError('key reset enabler must be 4 bytes')
    return bytes([0xC1, 0xE3]) + bytes(key_reset_enabler) + bytes([0, (param_len >> 8) & 0xFF, param_len & 0xFF, 0])


def cdb_read_handy_store(block, count=1):
    return bytes([0xD8, 0]) + struct.pack('>I', block) + bytes([0, (count >> 8) & 0xFF, count & 0xFF, 0])


def cdb_write_handy_store(block, count=1):
    return bytes([0xDA, 0]) + struct.pack('>I', block) + bytes([0, (count >> 8) & 0xFF, count & 0xFF, 0])


# --- parameter blocks ---------------------------------------------------------

def parse_encryption_status(data):
    if len(data) < 16:
        raise ProtocolError('encryption status response too short (%d bytes)' % len(data))
    if data[0] != 0x45:
        raise ProtocolError('unexpected encryption status signature 0x%02x' % data[0])
    security = data[3]
    cipher = data[4]
    password_length = struct.unpack('>H', bytes(data[6:8]))[0]
    key_reset_enabler = bytes(data[8:12])
    count = data[15]
    ciphers = list(bytes(data[16:16 + count]))
    return EncryptionStatus(security, cipher, password_length, key_reset_enabler, ciphers)


def password_blob_length(status):
    """Length in bytes of the password blob the drive expects."""
    if status.password_length in (16, 32):
        return status.password_length
    if status.cipher in AES128_CIPHERS:
        return 16
    if status.cipher in AES256_CIPHERS or status.cipher == FDE_CIPHER:
        return 32
    raise ProtocolError('cannot determine password length for cipher 0x%02x' % status.cipher)


def derive_password_blob(password, block=None, length=32):
    """Turn a user password into the binary blob the drive expects.

    Matches WD Security: UTF-16LE(salt + password), then SHA-256 applied
    `iterations` times. AES-128 drives take the first 16 bytes; the vendor
    algorithm for those drives is not publicly known, so that is a best effort.
    """
    block = block or SecurityBlock()
    data = (block.salt + password).encode('utf-16-le')
    for _ in range(block.iterations):
        data = sha256(data).digest()
    return data[:length]


def build_unlock_param(blob):
    return bytes([0x45, 0, 0, 0, 0, 0]) + struct.pack('>H', len(blob)) + blob


def build_change_password_param(length, old_blob=None, new_blob=None):
    """Parameter block for CHANGE ENCRYPTION PASSPHRASE.

    old_blob None means "enable security" (drive default is the old password).
    new_blob None means "disable security" (drive default becomes the new one).
    Both None is invalid. The flag byte follows the reference implementations:
    0x01 when only a new password is supplied, 0x10 when only the old one is.
    """
    if old_blob is None and new_blob is None:
        raise ValueError('at least one of old_blob and new_blob is required')
    flags = 0
    if old_blob is not None:
        if len(old_blob) != length:
            raise ValueError('old password blob must be %d bytes' % length)
        flags |= 0x10
    else:
        old_blob = bytes(length)
    if new_blob is not None:
        if len(new_blob) != length:
            raise ValueError('new password blob must be %d bytes' % length)
        flags |= 0x01
    else:
        new_blob = bytes(length)
    if flags & 0x11 == 0x11:
        flags &= 0xEE
    return bytes([0x45, 0, 0, flags, 0, 0]) + struct.pack('>H', length) + old_blob + new_blob


def build_reset_key_param(cipher, key=None, combine=None):
    """Parameter block for RESET DATA ENCRYPTION KEY (the secure erase).

    Full-disk-encryption drives generate their own key and take an empty KEY.
    Bridge-encrypted drives take a key of the cipher's length, in bits.
    """
    if cipher in AES128_CIPHERS:
        key_len = 16
    elif cipher in AES256_CIPHERS:
        key_len = 32
    elif cipher == FDE_CIPHER:
        key_len = 0
    else:
        raise ProtocolError('unsupported cipher 0x%02x for key reset' % cipher)
    if key is None:
        key = os.urandom(key_len)
    if len(key) != key_len:
        raise ValueError('key must be %d bytes for cipher 0x%02x' % (key_len, cipher))
    if combine is None:
        combine = 1 if key_len else 0
    return bytes([0x45, 0, 0, 1 if combine else 0, cipher, 0]) + struct.pack('>H', key_len * 8) + key


# --- handy store blocks -------------------------------------------------------

def handy_store_checksum(block):
    """Checksum used by WD utilities: bytes 0..509 plus byte 0 again, negated."""
    total = sum(block[:510]) + block[0]
    return (-total) & 0xFF


def _utf16_field(text, byte_len):
    raw = text.encode('utf-16-le')[:byte_len]
    if len(raw) % 2:
        raw = raw[:-1]
    return raw.ljust(byte_len, b'\x00')


def _utf16_decode(raw):
    text = raw.decode('utf-16-le', errors='replace')
    nul = text.find('\x00')
    return text if nul < 0 else text[:nul]


def parse_security_block(data):
    """Return a SecurityBlock, or None when the block is not initialised."""
    if len(data) < HANDY_BLOCK_SIZE:
        raise ProtocolError('handy store block too short (%d bytes)' % len(data))
    data = bytes(data[:HANDY_BLOCK_SIZE])
    if data[:4] != SECURITY_BLOCK_SIGNATURE:
        return None
    if handy_store_checksum(data) != data[511]:
        # Some WD utility versions count byte 0 once, not twice. Byte 0 is 0x00
        # in a valid block so both formulas agree; anything else is corrupt.
        raise ProtocolError('security block checksum mismatch')
    iterations = struct.unpack('<I', data[8:12])[0]
    salt = _utf16_decode(data[12:20])
    hint = _utf16_decode(data[24:226])
    return SecurityBlock(iterations, salt, hint)


def build_security_block(block):
    if block.iterations <= 0:
        raise ValueError('iterations must be positive')
    if len(block.salt) > SALT_MAX_CHARS:
        raise ValueError('salt is at most %d characters' % SALT_MAX_CHARS)
    hint = block.hint[:HINT_MAX_CHARS]
    data = bytearray(HANDY_BLOCK_SIZE)
    data[0:4] = SECURITY_BLOCK_SIGNATURE
    data[8:12] = struct.pack('<I', block.iterations)
    data[12:20] = _utf16_field(block.salt, 8)
    data[24:226] = _utf16_field(hint, 202)
    data[511] = handy_store_checksum(data)
    return bytes(data)


def parse_user_block(data):
    """Return the drive label stored in handy store block 2, or None."""
    if len(data) < HANDY_BLOCK_SIZE:
        raise ProtocolError('handy store block too short (%d bytes)' % len(data))
    data = bytes(data[:HANDY_BLOCK_SIZE])
    if data[:4] != USER_BLOCK_SIGNATURE:
        return None
    if handy_store_checksum(data) != data[511]:
        raise ProtocolError('user block checksum mismatch')
    return _utf16_decode(data[8:72])


def build_user_block(label):
    data = bytearray(HANDY_BLOCK_SIZE)
    data[0:4] = USER_BLOCK_SIGNATURE
    data[8:72] = _utf16_field(label[:LABEL_MAX_CHARS], 64)
    data[511] = handy_store_checksum(data)
    return bytes(data)


# --- sense data ---------------------------------------------------------------

class SenseInfo:
    __slots__ = ('key', 'asc', 'ascq')

    def __init__(self, key, asc, ascq):
        self.key = key
        self.asc = asc
        self.ascq = ascq

    def __eq__(self, other):
        return isinstance(other, SenseInfo) and (self.key, self.asc, self.ascq) == (other.key, other.asc, other.ascq)

    def __repr__(self):
        return 'SenseInfo(key=0x%x, asc=0x%02x, ascq=0x%02x)' % (self.key, self.asc, self.ascq)


def parse_sense(sense):
    """Decode fixed or descriptor format sense data. Returns None if empty."""
    if not sense:
        return None
    sense = bytes(sense)
    fmt = sense[0] & 0x7F
    if fmt in (0x70, 0x71) and len(sense) >= 14:
        return SenseInfo(sense[2] & 0x0F, sense[12], sense[13])
    if fmt in (0x72, 0x73) and len(sense) >= 4:
        return SenseInfo(sense[1] & 0x0F, sense[2], sense[3])
    return None


SENSE_MESSAGES = {
    (0x5, 0x74, 0x40): 'The drive rejected the password.',
    (0x5, 0x74, 0x80): 'Too many failed attempts. Unplug the drive, plug it back in and try again.',
    (0x5, 0x74, 0x81): 'The drive is not in the right state for this operation.',
    (0x5, 0x24, 0x00): 'The drive rejected the command format (invalid field in CDB).',
    (0x5, 0x26, 0x00): 'The drive rejected the command data (invalid field in parameter list).',
    (0x5, 0x20, 0x00): 'This device does not support WD security commands on this node.',
    (0x7, 0x74, 0x71): 'The drive is locked. Unlock it first.',
}

SENSE_KEY_NAMES = {
    0x0: 'No Sense', 0x1: 'Recovered Error', 0x2: 'Not Ready', 0x3: 'Medium Error',
    0x4: 'Hardware Error', 0x5: 'Illegal Request', 0x6: 'Unit Attention',
    0x7: 'Data Protect', 0xB: 'Aborted Command',
}


def describe_sense(info):
    if info is None:
        return 'No sense data returned.'
    msg = SENSE_MESSAGES.get((info.key, info.asc, info.ascq))
    key_name = SENSE_KEY_NAMES.get(info.key, 'Sense key 0x%x' % info.key)
    detail = '%s, ASC=0x%02x, ASCQ=0x%02x' % (key_name, info.asc, info.ascq)
    return '%s (%s)' % (msg, detail) if msg else detail


def is_wrong_password(info):
    return info is not None and (info.key, info.asc, info.ascq) == (0x5, 0x74, 0x40)


def is_attempts_blocked(info):
    return info is not None and (info.key, info.asc, info.ascq) == (0x5, 0x74, 0x80)


def is_wrong_state(info):
    return info is not None and (info.key, info.asc, info.ascq) == (0x5, 0x74, 0x81)
