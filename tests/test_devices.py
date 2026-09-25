import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

from wdpassport import devices  # noqa: E402

LSBLK_JSON = '''{
   "blockdevices": [
      {"name":"sdb","type":"disk","fstype":null,"label":null,"size":2000398934016,"mountpoint":null,"uuid":null,
         "children": [
            {"name":"sdb1","type":"part","fstype":"ntfs","label":"My Passport","size":2000397795328,"mountpoint":null,"uuid":"48C8"}
         ]
      }
   ]
}'''


class MountOptionTests(unittest.TestCase):
    def setUp(self):
        self.user = devices.DesktopUser('alice', 1000, 1000, '/home/alice')

    def test_ntfs_gets_user_ownership(self):
        opts = devices.mount_options('ntfs', self.user)
        self.assertIn('uid=1000', opts)
        self.assertIn('gid=1000', opts)
        self.assertIn('umask=022', opts)
        self.assertIn('windows_names', opts)

    def test_exfat_and_vfat(self):
        self.assertIn('uid=1000', devices.mount_options('exfat', self.user))
        vfat = devices.mount_options('vfat', self.user)
        self.assertIn('utf8', vfat)
        self.assertIn('uid=1000', vfat)

    def test_ext4_has_no_ownership_options(self):
        opts = devices.mount_options('ext4', self.user)
        self.assertFalse(any(o.startswith('uid=') for o in opts))
        self.assertEqual(opts, ['nosuid', 'nodev'])

    def test_no_user_means_no_mapping(self):
        self.assertEqual(devices.mount_options('ntfs', None), ['nosuid', 'nodev'])


class MountPathTests(unittest.TestCase):
    def test_safe_mount_name(self):
        self.assertEqual(devices.safe_mount_name('My Passport'), 'My Passport')
        self.assertEqual(devices.safe_mount_name('../etc/passwd'), 'etcpasswd')
        self.assertEqual(devices.safe_mount_name(''), 'wd-drive')
        self.assertEqual(devices.safe_mount_name('  weird\t name  '), 'weird name')

    def test_choose_mount_dir_prefers_media_user(self):
        user = devices.DesktopUser('alice', 1000, 1000, '/home/alice')
        with mock.patch.object(devices.os.path, 'isdir', side_effect=lambda p: p == '/media/alice'), \
                mock.patch.object(devices.os.path, 'exists', return_value=False):
            self.assertEqual(devices.choose_mount_dir('Vol', user), '/media/alice/Vol')

    def test_choose_mount_dir_falls_back_to_mnt(self):
        with mock.patch.object(devices.os.path, 'isdir', return_value=False), \
                mock.patch.object(devices.os.path, 'exists', return_value=False):
            self.assertEqual(devices.choose_mount_dir('Vol', None), '/mnt/Vol')

    def test_unique_dir_skips_busy_paths(self):
        existing = {'/mnt/Vol'}
        with mock.patch.object(devices.os.path, 'exists', side_effect=lambda p: p in existing), \
                mock.patch.object(devices.os.path, 'isdir', return_value=True), \
                mock.patch.object(devices.os, 'listdir', return_value=['file']), \
                mock.patch.object(devices, 'is_mountpoint', return_value=True):
            self.assertEqual(devices.unique_dir('/mnt/Vol'), '/mnt/Vol-2')


class DiscoveryTests(unittest.TestCase):
    def test_find_wd_disks_case_insensitive_and_dedup(self):
        entries = ['usb-WD_My_Passport_25E1_1234-0:0', 'usb-WD_My_Passport_25E1_1234-0:0-part1',
                   'usb-wd_Elements_5678-0:0', 'ata-Samsung_SSD', 'usb-WD_Virtual_CD-0:1']
        targets = {
            '/dev/disk/by-id/usb-WD_My_Passport_25E1_1234-0:0': '/dev/sdb',
            '/dev/disk/by-id/usb-WD_My_Passport_25E1_1234-0:0-part1': '/dev/sdb1',
            '/dev/disk/by-id/usb-wd_Elements_5678-0:0': '/dev/sdc',
            '/dev/disk/by-id/usb-WD_Virtual_CD-0:1': '/dev/sr0',
        }
        with mock.patch.object(devices.os.path, 'isdir', return_value=True), \
                mock.patch.object(devices.os, 'listdir', return_value=entries), \
                mock.patch.object(devices.os.path, 'islink', return_value=True), \
                mock.patch.object(devices.os.path, 'realpath', side_effect=lambda p: targets.get(p, p)):
            self.assertEqual(devices.find_wd_disks(), ['sdb', 'sdc'])

    def test_list_partitions_parses_lsblk_json(self):
        with mock.patch.object(devices, 'run_cmd', return_value=(LSBLK_JSON, '', 0)):
            parts = devices.list_partitions('sdb')
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].node, '/dev/sdb1')
        self.assertEqual(parts[0].fstype, 'ntfs')
        self.assertEqual(parts[0].label, 'My Passport')
        self.assertEqual(parts[0].mountpoint, '')

    def test_list_partitions_survives_bad_output(self):
        with mock.patch.object(devices, 'run_cmd', return_value=('not json', '', 0)):
            self.assertEqual(devices.list_partitions('sdb'), [])
        with mock.patch.object(devices, 'run_cmd', return_value=('', 'boom', 1)):
            self.assertEqual(devices.list_partitions('sdb'), [])

    def test_normalize_id_path(self):
        self.assertEqual(devices.normalize_id_path('pci-0000:03:00.4-usb-0:1:1.0-scsi-0:0:0:0'), 'pci-0000:03:00.4-usb-0:1:1.0')
        self.assertEqual(devices.normalize_id_path(''), '')

    def test_control_node_candidates_prefers_matching_enclosure(self):
        drive = devices.Drive('sdb')
        drive.id_path = 'pci-0000:03:00.4-usb-0:1:1.0'
        props = {
            '/dev/sg1': {'ID_PATH': 'pci-0000:03:00.4-usb-0:1:1.0-scsi-0:0:0:1'},
            '/dev/sg3': {'ID_PATH': 'pci-0000:00:14.0-usb-0:2:1.0-scsi-0:0:0:1'},
        }
        with mock.patch.object(devices, 'find_sg_devices', return_value=['sg1', 'sg3']), \
                mock.patch.object(devices, 'udev_properties', side_effect=lambda n: props.get(n, {})), \
                mock.patch.object(devices, 'sg_for_disk', return_value='sg0'):
            self.assertEqual(devices.control_node_candidates(drive), ['/dev/sg1', '/dev/sg0', '/dev/sdb'])

    def test_control_node_candidates_without_udev_match_tries_all_enclosures(self):
        drive = devices.Drive('sdb')
        with mock.patch.object(devices, 'find_sg_devices', return_value=['sg2']), \
                mock.patch.object(devices, 'udev_properties', return_value={}), \
                mock.patch.object(devices, 'sg_for_disk', return_value=None):
            self.assertEqual(devices.control_node_candidates(drive), ['/dev/sg2', '/dev/sdb'])

    def test_human_size(self):
        self.assertEqual(devices.human_size(2000398934016), '2.0 TB')
        self.assertEqual(devices.human_size(0), '0 B')
        self.assertEqual(devices.human_size(512), '512 B')


class DesktopUserTests(unittest.TestCase):
    def test_pkexec_uid_wins(self):
        entry = mock.Mock(pw_name='alice', pw_uid=1000, pw_gid=1000, pw_dir='/home/alice')
        with mock.patch.dict(devices.os.environ, {'PKEXEC_UID': '1000', 'SUDO_UID': '1001'}), \
                mock.patch.object(devices.pwd, 'getpwuid', return_value=entry):
            user = devices.desktop_user()
        self.assertEqual(user.name, 'alice')

    def test_root_is_not_a_desktop_user(self):
        with mock.patch.dict(devices.os.environ, {'PKEXEC_UID': '0'}, clear=True):
            self.assertIsNone(devices.desktop_user())

    def test_no_env_means_none(self):
        with mock.patch.dict(devices.os.environ, {}, clear=True):
            self.assertIsNone(devices.desktop_user())


class DriveDisplayTests(unittest.TestCase):
    def test_display_name_and_masked_serial(self):
        d = devices.Drive('sdb')
        d.vendor = 'WD'
        d.model = 'My_Passport_25E1'
        d.serial = '575838314134373750484331'
        self.assertEqual(d.display_name, 'WD My Passport 25E1')
        self.assertEqual(d.masked_serial, '575…4331')
        d.vendor = 'Western Digital'
        d.model = 'Western_Digital_Elements'
        self.assertEqual(d.display_name, 'Western Digital Elements')


if __name__ == '__main__':
    unittest.main(verbosity=2)
