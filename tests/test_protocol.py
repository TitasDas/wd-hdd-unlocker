import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

from wdpassport import protocol  # noqa: E402


class PasswordDerivationTests(unittest.TestCase):
    def test_matches_cookpw_reference(self):
        proc = subprocess.run([sys.executable, os.path.join(ROOT, 'app', 'cookpw.py'), 'correct horse'],
                              capture_output=True, check=True)
        expected = proc.stdout[8:]
        self.assertEqual(protocol.derive_password_blob('correct horse'), expected)
        self.assertEqual(protocol.build_unlock_param(expected), proc.stdout)

    def test_salt_and_iterations_from_block_change_result(self):
        default = protocol.derive_password_blob('pw')
        other = protocol.derive_password_blob('pw', protocol.SecurityBlock(iterations=1001))
        salted = protocol.derive_password_blob('pw', protocol.SecurityBlock(salt='ABCD'))
        self.assertNotEqual(default, other)
        self.assertNotEqual(default, salted)
        self.assertEqual(len(default), 32)

    def test_aes128_truncates_to_16_bytes(self):
        self.assertEqual(len(protocol.derive_password_blob('pw', length=16)), 16)


class CdbTests(unittest.TestCase):
    def test_encryption_status_cdb(self):
        self.assertEqual(protocol.cdb_encryption_status().hex(), 'c0450000000000003000')

    def test_unlock_cdb_matches_upstream_for_aes256(self):
        self.assertEqual(protocol.cdb_unlock(40).hex(), 'c1e10000000000002800')

    def test_change_password_cdb_matches_upstream(self):
        self.assertEqual(protocol.cdb_change_password(8 + 64).hex(), 'c1e20000000000004800')

    def test_reset_key_cdb_carries_enabler(self):
        cdb = protocol.cdb_reset_key(b'\xde\xad\xbe\xef', 40)
        self.assertEqual(cdb.hex(), 'c1e3deadbeef00002800')

    def test_handy_store_cdbs(self):
        self.assertEqual(protocol.cdb_read_handy_store(1).hex(), 'd8000000000100000100')
        self.assertEqual(protocol.cdb_write_handy_store(2).hex(), 'da000000000200000100')


class ParameterBlockTests(unittest.TestCase):
    def test_change_password_flags(self):
        old = b'\x01' * 32
        new = b'\x02' * 32
        enable = protocol.build_change_password_param(32, None, new)
        disable = protocol.build_change_password_param(32, old, None)
        change = protocol.build_change_password_param(32, old, new)
        self.assertEqual(enable[3], 0x01)
        self.assertEqual(enable[8:40], bytes(32))
        self.assertEqual(enable[40:72], new)
        self.assertEqual(disable[3], 0x10)
        self.assertEqual(disable[40:72], bytes(32))
        self.assertEqual(change[3], 0x00)
        self.assertEqual(change[6:8], b'\x00\x20')
        self.assertEqual(len(change), 72)
        with self.assertRaises(ValueError):
            protocol.build_change_password_param(32, None, None)
        with self.assertRaises(ValueError):
            protocol.build_change_password_param(32, b'short', new)

    def test_reset_key_param_for_aes_and_fde(self):
        aes = protocol.build_reset_key_param(0x28, key=b'k' * 32)
        self.assertEqual(aes[0], 0x45)
        self.assertEqual(aes[3], 1)
        self.assertEqual(aes[4], 0x28)
        self.assertEqual(aes[6:8], (256).to_bytes(2, 'big'))
        self.assertEqual(len(aes), 40)
        fde = protocol.build_reset_key_param(0x30)
        self.assertEqual(fde[3], 0)
        self.assertEqual(fde[6:8], b'\x00\x00')
        self.assertEqual(len(fde), 8)
        with self.assertRaises(protocol.ProtocolError):
            protocol.build_reset_key_param(0x99)

    def test_status_parse(self):
        data = bytearray(48)
        data[0] = 0x45
        data[3] = 0x01
        data[4] = 0x28
        data[6:8] = b'\x00\x20'
        data[8:12] = b'\x11\x22\x33\x44'
        data[15] = 2
        data[16:18] = b'\x28\x30'
        st = protocol.parse_encryption_status(bytes(data))
        self.assertTrue(st.is_locked)
        self.assertEqual(st.cipher_name, 'AES-256 XTS')
        self.assertEqual(st.password_length, 32)
        self.assertEqual(st.key_reset_enabler, b'\x11\x22\x33\x44')
        self.assertEqual(st.ciphers, [0x28, 0x30])
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_encryption_status(b'\x00' * 48)

    def test_password_blob_length_falls_back_to_cipher(self):
        st = protocol.EncryptionStatus(1, 0x18, 0, b'', [])
        self.assertEqual(protocol.password_blob_length(st), 16)
        st = protocol.EncryptionStatus(1, 0x30, 0, b'', [])
        self.assertEqual(protocol.password_blob_length(st), 32)


class HandyStoreTests(unittest.TestCase):
    def test_security_block_round_trip(self):
        block = protocol.SecurityBlock(1000, 'WDC.', 'my dog’s name')
        raw = protocol.build_security_block(block)
        self.assertEqual(len(raw), 512)
        self.assertEqual(raw[:4], b'\x00\x01DW')
        self.assertEqual(raw[8:12], (1000).to_bytes(4, 'little'))
        self.assertEqual(raw[12:20], 'WDC.'.encode('utf-16-le'))
        self.assertEqual(protocol.parse_security_block(raw), block)

    def test_checksum_matches_reference_formula(self):
        raw = bytearray(protocol.build_security_block(protocol.SecurityBlock(hint='x')))
        total = sum(raw[:510]) + raw[0]
        self.assertEqual(raw[511], (-total) & 0xFF)
        self.assertEqual((sum(raw[:511]) + raw[0] + raw[511]) & 0xFF, 0)

    def test_corrupt_checksum_rejected_and_blank_block_is_none(self):
        raw = bytearray(protocol.build_security_block(protocol.SecurityBlock()))
        raw[511] ^= 0xFF
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_security_block(bytes(raw))
        self.assertIsNone(protocol.parse_security_block(bytes(512)))

    def test_hint_is_truncated_to_101_chars(self):
        block = protocol.SecurityBlock(hint='h' * 200)
        parsed = protocol.parse_security_block(protocol.build_security_block(block))
        self.assertEqual(len(parsed.hint), 101)

    def test_user_block_round_trip(self):
        raw = protocol.build_user_block('Team Drive')
        self.assertEqual(protocol.parse_user_block(raw), 'Team Drive')


class SenseTests(unittest.TestCase):
    def test_fixed_format(self):
        sense = bytes([0x70, 0, 0x05] + [0] * 9 + [0x74, 0x40] + [0] * 4)
        info = protocol.parse_sense(sense)
        self.assertEqual(info, protocol.SenseInfo(5, 0x74, 0x40))
        self.assertTrue(protocol.is_wrong_password(info))
        self.assertIn('rejected the password', protocol.describe_sense(info))

    def test_descriptor_format(self):
        info = protocol.parse_sense(bytes([0x72, 0x05, 0x74, 0x80, 0, 0, 0, 0]))
        self.assertTrue(protocol.is_attempts_blocked(info))

    def test_empty(self):
        self.assertIsNone(protocol.parse_sense(b''))
        self.assertEqual(protocol.describe_sense(None), 'No sense data returned.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
