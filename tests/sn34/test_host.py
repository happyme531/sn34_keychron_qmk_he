"""Raw HID configuration needs only the selected keyboard's standard interface."""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'util/sn34'))
import device as device_commands


class Device:
    def __init__(self):
        self.pending = None
        self.requests = []

    def open_path(self, path): self.path = path
    def close(self): pass
    def set_nonblocking(self, value): pass

    def write(self, data):
        packet = bytes(data[1:])
        self.requests.append(packet)
        reply = bytearray(packet)
        if packet[0] == 1: reply[1:3] = bytes((0, 12))
        elif packet[0] == 4: reply[4:6] = bytes((0, 4))
        elif packet[:2] == bytes((0xa9, 0x10)): reply[2:4] = bytes((0, 3))
        elif packet[0] == 0xa1: reply[1:8] = b'v2.0.0\0'
        self.pending = list(reply)
        return len(data)

    def read(self, size, *args):
        reply = self.pending
        self.pending = None
        return reply or []


class HostSelection(unittest.TestCase):
    def setUp(self):
        self.device = Device()
        entries = [dict(usage_page=0xff60, usage=0x61, serial_number=serial, path=serial.encode())
                   for serial in ('ONE', 'TWO')]
        self.hid = SimpleNamespace(enumerate=Mock(return_value=entries), device=lambda: self.device)
        self.addCleanup(patch.stopall)
        patch.object(device_commands, 'hid', self.hid).start()
        patch.dict('os.environ', SN34_KEYBOARD='sn34_test', SN34_DEVICE_SERIAL='TWO').start()

    def test_identity_and_serial_select_exactly_one_device(self):
        raw = device_commands.Raw()
        self.assertEqual(self.device.path, b'TWO')
        self.hid.enumerate.assert_called_once_with(0xfeed, 0x34)
        raw.close()

    def test_ambiguous_devices_require_a_selection(self):
        with patch.dict('os.environ', SN34_DEVICE_SERIAL=''):
            with self.assertRaisesRegex(RuntimeError, 'select'):
                device_commands.Raw()

    def test_get_and_status_work_with_only_raw_hid(self):
        for command in (['get', '--key', 'T0'], ['status']):
            with patch.object(sys, 'argv', ['device_commands.py', *command, '--worker']):
                output = io.StringIO()
                with contextlib.redirect_stdout(output): device_commands.main()
                result = json.loads(output.getvalue())
            if command[0] == 'get': self.assertEqual(result['keycode'], '0x0004')
            else:
                self.assertEqual(result['profile_count'], 3)
                self.assertEqual(result['firmware'], 'v2.0.0')
        self.assertTrue(all(len(packet) == 32 for packet in self.device.requests))


if __name__ == '__main__': unittest.main()
