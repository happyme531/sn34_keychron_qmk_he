"""Check optional packaging against the actual, ordinary QMK build products."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'util/sn34'))
from emulator import FIRMWARE
from target import keyboard_name
from export import definitions
from firmware import keyboard_definition, keyboard_layout
from package import wrap_updater, preserve_settings
from target import ROOT


class StandardBuildProducts(unittest.TestCase):
    def test_elf_load_image_matches_qmk_objcopy(self):
        self.assertEqual(FIRMWARE.code, FIRMWARE.path.with_suffix('.bin').read_bytes())

    def test_application_preserves_code_and_reserves_settings(self):
        image = FIRMWARE.application()
        memory = FIRMWARE.memory
        self.assertEqual(len(image), memory['app_size'])
        self.assertEqual(image[:len(FIRMWARE.code)], FIRMWARE.code)
        self.assertFalse(any(image[memory['code_limit']:memory['eeprom_end']]))
        self.assertEqual(int.from_bytes(image[memory['footer_address']:][:4], 'little'), memory['footer_magic'])

    def test_configurator_matches_compiled_features(self):
        via, launcher = definitions(FIRMWARE)
        self.assertEqual(via['menus'], launcher['menus'])
        self.assertEqual(bool(via['menus']), FIRMWARE.features['rgb'])
        self.assertEqual(via['matrix'], launcher['matrix'])

    def test_export_accepts_a_renamed_layout_and_an_explicit_layout_choice(self):
        expected = definitions(FIRMWARE)
        board = keyboard_definition()
        keys = keyboard_layout(board)
        board['layouts'] = {'LAYOUT_ansi': {'layout': keys}}
        with patch('export.keyboard_definition', return_value=board), patch.dict('os.environ', SN34_LAYOUT=''):
            self.assertEqual(definitions(FIRMWARE), expected)
            board['layouts']['LAYOUT_iso'] = {'layout': keys}
            with self.assertRaisesRegex(ValueError, 'Select --layout'):
                definitions(FIRMWARE)
            self.assertEqual(definitions(FIRMWARE, layout='LAYOUT_iso'), expected)

    def test_wrong_updater_template_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'template'):
            wrap_updater(b'wrong executable', b'', {'template_sha256': '0'*64})

    def test_wrong_keyboard_identity_is_rejected(self):
        other = 'sn34_test' if keyboard_name() == 'battle68' else 'battle68'
        with self.assertRaisesRegex(ValueError, 'identity'):
            FIRMWARE.validate_keyboard(other)

    @unittest.skipUnless(keyboard_name() == 'battle68', 'Battle68 compatibility fixture')
    def test_packaging_copies_legacy_committed_banks_unchanged(self):
        memory = FIRMWARE.memory
        banks = (ROOT/'tests/sn34/boards/battle68/fixtures/sn34_v36_eeprom.bin').read_bytes()
        backup = bytearray(memory['app_size'])
        backup[memory['code_limit']:memory['eeprom_end']] = banks
        image, record = preserve_settings(FIRMWARE.application(), bytes(backup), FIRMWARE)
        self.assertEqual(image[memory['code_limit']:memory['eeprom_end']], banks)
        self.assertEqual(record['banks'], 1)
        backup[memory['code_limit'] + 17] ^= 1
        with self.assertRaisesRegex(ValueError, 'committed settings bank'):
            preserve_settings(FIRMWARE.application(), bytes(backup), FIRMWARE)


if __name__ == '__main__':
    unittest.main()
