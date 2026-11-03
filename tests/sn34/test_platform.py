"""Platform boundaries: inherited metadata, memory mapping and legacy policy."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from dataclasses import replace
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent / 'common'),
               str(Path(__file__).resolve().parents[2] / 'util/sn34')]
import firmware
import model
import storage
from emulator import FIRMWARE
from keyboard import Keyboard
from settings import BATTLE68_EEPROM_MAGIC, migrated_payload, read_banks, snapshot_image


class PlatformContracts(unittest.TestCase):
    def test_layout_selection_accepts_names_aliases_and_requires_an_explicit_choice(self):
        ansi = [{'matrix': [0, 0], 'label': 'ANSI'}]
        iso = [{'matrix': [0, 1], 'label': 'ISO'}]
        board = {'layouts': {'LAYOUT_ansi': {'layout': ansi}}}
        with patch.dict('os.environ', SN34_LAYOUT=''):
            self.assertEqual(firmware.keyboard_layout(board), ansi)
            board['layouts']['LAYOUT_iso'] = {'layout': iso}
            board['layout_aliases'] = {'LAYOUT': 'LAYOUT_ansi'}
            with self.assertRaisesRegex(ValueError, 'Select --layout'):
                firmware.keyboard_layout(board)
            self.assertEqual(firmware.keyboard_layout(board, 'LAYOUT_iso'), iso)
            self.assertEqual(firmware.keyboard_layout(board, 'LAYOUT'), ansi)
            with self.assertRaisesRegex(ValueError, 'Select --layout'):
                firmware.keyboard_layout(board, 'LAYOUT_missing')
        with patch.dict('os.environ', SN34_LAYOUT='LAYOUT_iso'):
            self.assertEqual(firmware.keyboard_layout(board), iso)

    def test_usb_power_and_hid_intervals_at_both_speeds(self):
        usb = firmware.keyboard_definition()['usb']
        interval = usb.get('polling_interval')
        high_speed = 4 + interval.bit_length() - 1 if interval else 1
        keyboard = Keyboard()
        for callback, expected in (('HAL_PCD_HighSpeedCallback', high_speed),
                                   ('HAL_PCD_ResetCallback', interval or 1)):
            keyboard.call(callback, 0)
            self.assertEqual(keyboard.setup(0x80, 6, 0x0200, 0, 512), 0)
            descriptor = keyboard.transfers[-1][1]
            self.assertEqual(descriptor[8], usb.get('max_power', 500) // 2)
            at, hid, endpoints = 0, False, 0
            while at < len(descriptor):
                size, kind = descriptor[at:at + 2]
                if kind == 4:
                    hid = descriptor[at + 5] == 3
                elif kind == 5 and hid:
                    self.assertEqual(descriptor[at + 6], expected)
                    endpoints += 1
                at += size
            self.assertGreater(endpoints, 0)

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
                'keyboard_name': 'Inherited board',
                'usb': {'vid': '0x1234'},
                'matrix_pins': {'rows': [None], 'cols': [None]},
                'rgb_matrix': {'layout': [{'matrix': [0, 0], 'x': 0, 'y': 0, 'flags': 4}]},
                'layouts': {'LAYOUT_ansi': {'layout': [{'matrix': [0, 0], 'x': 0, 'y': 0}]}}}))
            (child / 'keyboard.json').write_text(json.dumps({
                'usb': {'pid': '0x5678'},
                'layouts': {'LAYOUT_ansi': {'layout': [{'label': 'A'}]}}}))
            fixture = root / 'measured-board.json'
            fixture.write_text(json.dumps({'matrix': {}, 'keys': [{'matrix': [0, 0], 'raw_slot': 0}]}))
            with patch.object(firmware, 'ROOT', root), patch.dict('os.environ', SN34_KEYBOARD='example/ansi', SN34_LAYOUT=''):
                board = firmware.keyboard_definition('example/ansi')
                self.assertEqual(board['usb'], {'vid': '0x1234', 'pid': '0x5678'})
                self.assertEqual(board['layouts']['LAYOUT_ansi']['layout'][0],
                                 {'label': 'A', 'matrix': [0, 0], 'x': 0, 'y': 0})
                self.assertEqual(firmware.keyboard_file('board/configurator.json', 'example/ansi'), resource)
                measured = model.load_board(fixture)
                self.assertEqual(measured['matrix'], {'rows': 1, 'cols': 1})
                self.assertEqual(measured['keys'][0]['name'], 'A')
                self.assertEqual(measured['keys'][0]['led'], 0)
                self.assertEqual(measured['usb'], board['usb'])

    def test_new_board_versions_are_not_battle68_history(self):
        with TemporaryDirectory(dir=firmware.ROOT / '.build') as temporary:
            path = Path(temporary) / 'storage.json'
            fixture = json.loads(storage.STORAGE_FILE.read_text())
            fixture.update(eeprom_magic='0x12345678', eeprom_version=1)
            fixture.pop('eeprom_legacy_versions', None)
            path.write_text(json.dumps(fixture))
            layout = storage.load_storage(path)
        self.assertEqual(layout.eeprom_version, 1)
        self.assertEqual(layout.eeprom_legacy_versions, 0)
        memory = dict(FIRMWARE.memory, eeprom_magic=layout.eeprom_magic,
                      eeprom_version=1, eeprom_legacy_versions=0)
        payload = bytes([0xa5]) + bytes(memory['eeprom_size'] - 1)
        for version in (1, 2, 3, 5, 31):
            with self.subTest(version=version):
                image = snapshot_image(payload, dict(memory, eeprom_version=version))
                self.assertEqual(bool(storage.read_banks(image, layout)), version == 1)
                self.assertEqual(bool(read_banks(image, memory)), version == 1)
        # Future boards can declare their own current and legacy version numbers.
        layout = replace(layout, eeprom_version=6, eeprom_legacy_versions=1 << 5)
        memory.update(eeprom_version=6, eeprom_legacy_versions=1 << 5)
        for version in (1, 2, 5, 6):
            image = snapshot_image(payload, dict(memory, eeprom_version=version))
            self.assertEqual(bool(storage.read_banks(image, layout)), version in (5, 6))
            self.assertEqual(bool(read_banks(image, memory)), version in (5, 6))

    def test_only_battle68_v2_to_v3_moves_the_calibration_payload(self):
        payload = bytes(range(100)) + bytes(FIRMWARE.memory['eeprom_size'] - 100)
        record = dict(version=2, payload=payload)
        memory = dict(FIRMWARE.memory, eeprom_magic=BATTLE68_EEPROM_MAGIC, eeprom_version=3)
        start = memory['eeprom_base'] + 1
        self.assertEqual(migrated_payload(record, memory), payload[:start + 1] + payload[start:-1])
        for changes in ({'eeprom_magic': 0x12345678}, {'eeprom_version': 4}):
            self.assertEqual(migrated_payload(record, dict(memory, **changes)), payload)
        # A non-Battle68 v2 payload may legitimately use its final macro bytes.
        payload = payload[:-2] + b'xy'
        self.assertEqual(migrated_payload(dict(version=2, payload=payload),
                                         dict(memory, eeprom_magic=0x12345678)), payload)

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
