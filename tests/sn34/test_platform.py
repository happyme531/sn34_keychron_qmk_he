"""Platform boundaries: inherited metadata, memory mapping and legacy policy."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent / 'common'),
               str(Path(__file__).resolve().parents[2] / 'util/sn34')]
import firmware
from emulator import FIRMWARE
from keyboard import Keyboard
from settings import read_banks, snapshot_image


class PlatformContracts(unittest.TestCase):
    def test_stock_he_inherits_common_identity_and_matrix(self):
        board = firmware.keyboard_definition('keychron/q1_he/ansi_encoder')
        parent = json.loads((firmware.ROOT / 'keyboards/keychron/q1_he/info.json').read_text())
        self.assertEqual(board['usb']['vid'], parent['usb']['vid'])
        self.assertEqual(board['usb']['pid'], '0x0B10')
        self.assertEqual(board['matrix_pins'], parent['matrix_pins'])

    def test_partial_layout_and_board_resource_are_inherited(self):
        with TemporaryDirectory(dir=firmware.ROOT / '.build') as temporary:
            root = Path(temporary)
            parent = root / 'keyboards/example'
            child = parent / 'ansi'
            child.mkdir(parents=True)
            (parent / 'board').mkdir()
            resource = parent / 'board/configurator.json'
            resource.write_text('{"layers": ["Base"]}')
            (parent / 'info.json').write_text(json.dumps({
                'usb': {'vid': '0x1234'},
                'layouts': {'LAYOUT': {'layout': [{'matrix': [0, 0], 'x': 0, 'y': 0}]}}}))
            (child / 'keyboard.json').write_text(json.dumps({
                'usb': {'pid': '0x5678'},
                'layouts': {'LAYOUT': {'layout': [{'label': 'A'}]}}}))
            with patch.object(firmware, 'ROOT', root):
                board = firmware.keyboard_definition('example/ansi')
                self.assertEqual(board['usb'], {'vid': '0x1234', 'pid': '0x5678'})
                self.assertEqual(board['layouts']['LAYOUT']['layout'][0],
                                 {'label': 'A', 'matrix': [0, 0], 'x': 0, 'y': 0})
                self.assertEqual(firmware.keyboard_file('board/configurator.json', 'example/ansi'), resource)

    def test_nonzero_user_rom_origin_is_rejected(self):
        memory = dict(FIRMWARE.memory, app_origin=0x1000)
        with self.assertRaisesRegex(ValueError, 'offset zero'):
            snapshot_image(bytes(memory['eeprom_size']), memory)
        with self.assertRaisesRegex(ValueError, 'offset zero'):
            read_banks(bytes(memory['app_size']), memory)

    def test_firmware_and_host_accept_only_declared_legacy_versions(self):
        memory = FIRMWARE.memory
        for version in (1, 2, 3, 4, 31):
            with self.subTest(version=version):
                payload = bytearray(memory['eeprom_size'])
                payload[0] = 0xa5
                image = snapshot_image(payload, dict(memory, eeprom_version=version))
                supported = version == memory['eeprom_version'] or bool(memory['eeprom_legacy_versions'] & (1 << version))
                self.assertEqual(bool(read_banks(image, memory)), supported)
                keyboard = Keyboard()
                start = memory['code_limit']
                keyboard.u.mem_write(start, image[start:])
                keyboard.call('eeprom_driver_init')
                self.assertEqual(keyboard.call('eeprom_read_byte', 0), 0xa5 if supported else 0)


if __name__ == '__main__':
    unittest.main()
