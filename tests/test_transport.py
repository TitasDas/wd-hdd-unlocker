import ctypes
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

from wdpassport import protocol, transport  # noqa: E402


class SgIoHeaderTests(unittest.TestCase):
    def test_header_matches_kernel_layout(self):
        # sizeof(struct sg_io_hdr) is 88 on 64-bit Linux; status starts at 64.
        self.assertEqual(ctypes.sizeof(transport.SgIoHdr), 88 if ctypes.sizeof(ctypes.c_void_p) == 8 else 64)
        self.assertEqual(transport.SgIoHdr.status.offset, 64 if ctypes.sizeof(ctypes.c_void_p) == 8 else 44)

    def test_missing_node_is_unavailable(self):
        t = transport.SgIoTransport()
        with self.assertRaises(transport.TransportUnavailable):
            t.execute('/dev/definitely-not-a-device', protocol.cdb_encryption_status(), data_in_len=48)


class SgRawTests(unittest.TestCase):
    def test_sense_parsing_from_stderr(self):
        t = transport.SgRawTransport(binary='/bin/false')
        info = t._sense_from_text('SCSI Status: Check Condition\nSense key: Illegal Request ASC=74, ASCQ=40 (hex)')
        self.assertEqual(info, protocol.SenseInfo(0x5, 0x74, 0x40))
        self.assertIsNone(t._sense_from_text('garbage'))

    def test_execute_builds_expected_command_and_reads_output(self):
        t = transport.SgRawTransport(binary='/usr/bin/sg_raw')
        seen = {}

        def fake_run(args, capture_output, text, timeout):
            seen['args'] = args
            out_path = args[args.index('-o') + 1]
            with open(out_path, 'wb') as fh:
                fh.write(b'\x45' + bytes(47))
            return mock.Mock(returncode=0, stdout='', stderr='')

        with mock.patch.object(transport.subprocess, 'run', side_effect=fake_run):
            data = t.execute('/dev/sg1', protocol.cdb_encryption_status(), data_in_len=48)
        self.assertEqual(data[0], 0x45)
        self.assertEqual(seen['args'][0], '/usr/bin/sg_raw')
        self.assertIn('/dev/sg1', seen['args'])
        self.assertEqual(seen['args'][-10:], ['c0', '45', '00', '00', '00', '00', '00', '00', '30', '00'])

    def test_execute_raises_scsi_error_with_sense(self):
        t = transport.SgRawTransport(binary='/usr/bin/sg_raw')
        result = mock.Mock(returncode=2, stdout='', stderr='Sense key: Illegal Request ASC=74, ASCQ=40 (hex)')
        with mock.patch.object(transport.subprocess, 'run', return_value=result):
            with self.assertRaises(transport.ScsiError) as ctx:
                t.execute('/dev/sg1', protocol.cdb_unlock(40), data_out=bytes(40))
        self.assertTrue(protocol.is_wrong_password(ctx.exception.sense))


class ChainedTests(unittest.TestCase):
    def test_falls_back_when_first_unavailable(self):
        first = mock.Mock()
        first.name = 'first'
        first.execute.side_effect = transport.TransportUnavailable('nope')
        second = mock.Mock()
        second.name = 'second'
        second.execute.return_value = b'ok'
        chained = transport.ChainedTransport([first, second])
        self.assertEqual(chained.execute('/dev/sg0', b'\x00'), b'ok')
        self.assertEqual(chained.last_used, 'second')

    def test_scsi_error_is_not_retried_on_next_transport(self):
        first = mock.Mock()
        first.name = 'first'
        first.execute.side_effect = transport.ScsiError('bad')
        second = mock.Mock()
        chained = transport.ChainedTransport([first, second])
        with self.assertRaises(transport.ScsiError):
            chained.execute('/dev/sg0', b'\x00')
        second.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
