"""Check the frozen v36 matrix, defaults and persistent storage contract."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"common"))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import hashlib
import json
import re
from tempfile import TemporaryDirectory
import unittest
from target import ROOT
from model import load_board, matrix_digest, keyboard_definition
from storage import LEGACY_LAYOUT as LAYOUT, load_storage, read_banks, normalize_via_tag, STORAGE_FILE

FIXTURES = ROOT / "tests/sn34/boards/battle68/fixtures"
COMPAT = json.loads((FIXTURES / "sn34_v36_compatibility.json").read_text(encoding="utf-8"))


class CompatibilityContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="contract-test-", dir=ROOT / ".build")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_matrix_identity_matches_the_frozen_contract(self):
        board = load_board()
        self.assertEqual(matrix_digest(board["keys"]), COMPAT["matrix_sha256"])
        table=(ROOT/'keyboards/battle68/board/keys.inc').read_text(encoding='utf-8')
        actual=[{'raw_slot':int(raw),'matrix':[int(slot)//board['matrix']['cols'],int(slot)%board['matrix']['cols']]}
                for raw,slot,idle,bottom in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}',table)]
        self.assertEqual(matrix_digest(actual), COMPAT['matrix_sha256'])
        fn = next(k for k in board["keys"] if k["raw_slot"] == board["roles"]["fn"])
        self.assertEqual(fn["matrix"], [0, 0])
        definition = keyboard_definition()
        self.assertEqual({tuple(k["matrix"]) for k in definition["layouts"]["LAYOUT"]["layout"]},
                         {tuple(k["matrix"]) for k in board["keys"]})

    def test_default_keymap_calibration_and_led_tables_are_unchanged(self):
        digest = lambda value: hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()
        keymap = (ROOT/'keyboards/battle68/keymaps/default/keymap.c').read_text(encoding='utf-8')
        values = re.sub(r'\s+', '', keymap.split('=', 1)[1].split(';',1)[0])
        self.assertEqual(digest(values), COMPAT['default_keymap_values_sha256'])
        table = (ROOT / 'keyboards/battle68/board/keys.inc').read_text(encoding='utf-8')
        hall = [[int(row.split(',')[i]) for i in (1, 2, 3)]
                for row in re.findall(r'\{(\d+,\d+,\d+,\d+)\}', table)]
        self.assertEqual(digest(hall), COMPAT['hall_defaults_values_sha256'])
        board=load_board()
        leds=keyboard_definition()['rgb_matrix']['layout']
        matrix=[[255]*board['matrix']['cols'] for _ in range(board['matrix']['rows'])]
        for index,led in enumerate(leds):
            if 'matrix' in led:
                row,col=led['matrix'];matrix[row][col]=index
        values=[matrix,[[led['x'],led['y']] for led in leds],[led['flags'] for led in leds]]
        self.assertEqual(digest(values), COMPAT['rgb_layout_values_sha256'])

    def test_storage_schema_matches_installed_firmware(self):
        self.assertEqual(list(map(hex, LAYOUT.eeprom_banks)), COMPAT["eeprom_banks"])
        self.assertEqual(LAYOUT.eeprom_size, COMPAT["eeprom_size"])
        self.assertEqual(LAYOUT.eeprom_version, COMPAT["eeprom_version"])
        self.assertEqual(LAYOUT.via_eeprom_date, COMPAT["via_eeprom_date"])
        self.assertEqual(LAYOUT.eeprom_base, COMPAT["he_base"])
        for name in ("calibration_offset", "profiles_offset", "profile_size", "curve_offset", "controller_offset", "size"):
            self.assertEqual(LAYOUT.he[name], COMPAT["he_" + name])

    def test_real_v36_bank_parses_and_corruption_is_rejected(self):
        banks = (FIXTURES / "sn34_v36_eeprom.bin").read_bytes()
        self.assertEqual(hashlib.sha256(banks).hexdigest(), COMPAT["settings_fixture"]["bank_image_sha256"])
        image = bytearray(LAYOUT.app_size)
        image[LAYOUT.code_limit:LAYOUT.eeprom_end] = banks
        valid = read_banks(image)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["sequence"], COMPAT["settings_fixture"]["sequence"])
        image[valid[0]["bank"] + 17] ^= 1
        self.assertEqual(read_banks(image), [])

    def test_invalid_storage_regions_are_rejected(self):
        for changes in ({"page_size": 0}, {"eeprom_banks": ["0x79000", "0x79000"]}, {"footer_address": "0x79000"}):
            data = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
            data.update(changes)
            path = self.root / "storage.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_storage(path)

    def test_build_date_tags_migrate_without_accepting_an_invalid_via_cache(self):
        payload=bytearray(LAYOUT.eeprom_size)
        at=LAYOUT.via_magic_offset
        payload[at:at+3]=bytes.fromhex("261031")
        self.assertEqual(normalize_via_tag(payload,LAYOUT),bytes.fromhex("261031"))
        self.assertEqual(payload[at:at+3],LAYOUT.via_magic)
        payload[at:at+3]=bytes.fromhex("ffffff")
        with self.assertRaisesRegex(ValueError,"marked for reset"):
            normalize_via_tag(payload,LAYOUT)


if __name__ == "__main__":
    unittest.main()
