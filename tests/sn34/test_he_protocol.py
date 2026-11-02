"""Exercise shared HE handlers directly, without SN34's held-key/RGB policy."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
from keyboard import Keyboard, KEYS
from emulator import SCRATCH, SYMS, FIRMWARE


class SharedHeProtocol(unittest.TestCase):
    def setUp(self):
        self.keyboard = Keyboard()

    def command(self, payload):
        packet = bytes(payload).ljust(32, b'\0')
        guard = b'unchanged guard!'
        self.keyboard.u.mem_write(SCRATCH, packet + guard)
        before = len(self.keyboard.transfers)
        self.keyboard.call('analog_matrix_rx', SCRATCH, 32)
        self.keyboard.drain()
        self.assertEqual(bytes(self.keyboard.u.mem_read(SCRATCH + 32, len(guard))), guard)
        return [data for ep, data in self.keyboard.transfers[before:] if ep == 0x85][-1]

    def test_launcher_profile_name_request_fits_the_packet(self):
        reply = self.command((0xa9, 0x12, 0, 0, 0, 30))
        self.assertEqual(reply[:6], bytes((0xa9, 0x12, 0, 0, 0, 30)))
        profile = SYMS['profile']
        self.assertEqual(reply[6:], bytes(self.keyboard.u.mem_read(profile, 26)))
        size = FIRMWARE.symbols['profile']['st_size'] // 3
        reply = self.command((0xa9, 0x12, 0, (size - 1) & 255, (size - 1) >> 8, 1))
        self.assertEqual(reply[6], self.keyboard.u.mem_read(profile + size - 1, 1)[0])
        for offset in (size - 1, size + 1, 65535):
            self.assertEqual(self.command((0xa9, 0x12, 0, offset & 255, offset >> 8, 2))[0], 255)

    def test_invalid_writes_are_rejected_by_the_shared_handler(self):
        row, col = KEYS[0]['matrix']
        invalid = [
            (0xa9, 0x12, 255, 0, 0, 26),
            (0xa9, 0x12, 0, 0, 0, 31),
            (0xa9, 0x14, 0, 2, 0, 4, 4, 1),
            (0xa9, 0x14, 0, 1, 12, 40, 4, 0),
            (0xa9, 0x15, 0, 1, row, col, 0, 10, 10, 25, 22),
            (0xa9, 0x15, 0, 1, row, col, 0, 10, 8, 25, 25),
            (0xa9, 0x21, 0, 0, 10, 31, 10, 95, 40, 127),
            (0xa9, 0x21, 0, 0, 10, 31, 30, 95, 41, 127),
            (0xa9, 0x21, 0, 0, 10, 128, 30, 95, 40, 127),
            (0xa9, 0x23, 4),
        ]
        if not FIRMWARE.features['xinput']:
            invalid.append((0xa9, 0x23, 1))
        size = FIRMWARE.symbols['profile']['st_size']
        profiles = bytes(self.keyboard.u.mem_read(SYMS['profile'], size))
        curve = self.command((0xa9, 0x20))[2:10]
        revision = bytes(self.keyboard.u.mem_read(SYMS['sn34_eeprom_revision'], 4))
        for packet in invalid:
            with self.subTest(packet=packet):
                self.assertEqual(self.command(packet)[0], 255)
                self.assertEqual(bytes(self.keyboard.u.mem_read(SYMS['profile'], size)), profiles)
                self.assertEqual(bytes(self.keyboard.u.mem_read(SYMS['sn34_eeprom_revision'], 4)), revision)
                self.assertEqual(self.command((0xa9, 0x20))[2:10], curve)

    def test_global_threshold_changes_refresh_only_the_active_profile(self):
        key = KEYS[0]
        self.keyboard.call('dynamic_keymap_set_keycode', 0, *key['matrix'], 4)
        self.assertEqual(self.command((0xa9, 0x14, 1, 1, 30, 4, 4, 1))[2], 0)
        self.keyboard.travel_key(key, 100)
        self.keyboard.step()
        self.assertTrue(self.keyboard.pressed(4))
        self.keyboard.travel_key(key, 0)
        self.keyboard.step()
        self.assertEqual(self.command((0xa9, 0x14, 0, 1, 30, 4, 4, 1))[2], 0)
        self.keyboard.travel_key(key, 100)
        self.keyboard.step()
        self.assertFalse(self.keyboard.pressed(4))
        self.keyboard.travel_key(key, 210)
        self.keyboard.step()
        self.assertTrue(self.keyboard.pressed(4))


if __name__ == '__main__':
    unittest.main()
