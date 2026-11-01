"""Check the frozen v36 matrix, defaults and persistent storage contract."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from bat68_board import generate_board
from bat68_build_config import ROOT
from bat68_model import load_board, matrix_digest, keyboard_definition, sync_keyboard_definition
from bat68_storage import LAYOUT, load_storage, read_banks, normalize_via_tag, STORAGE_FILE

FIXTURES = ROOT / "tests/fixtures"
COMPAT = json.loads((FIXTURES / "bat68_v36_compatibility.json").read_text(encoding="utf-8"))


class CompatibilityContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="contract-test-", dir=ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_matrix_identity_matches_the_frozen_contract(self):
        board = load_board()
        self.assertEqual(matrix_digest(board["keys"]), COMPAT["matrix_sha256"])
        fn = next(k for k in board["keys"] if k["raw_slot"] == board["roles"]["fn"])
        self.assertEqual(fn["matrix"], [0, 0])
        definition = keyboard_definition(board)
        self.assertEqual({tuple(k["matrix"]) for k in definition["layouts"]["LAYOUT"]["layout"]},
                         {tuple(k["matrix"]) for k in board["keys"]})

    def test_default_keymap_calibration_and_led_tables_are_unchanged(self):
        generate_board(ROOT, self.root)
        for key, filename in (("default_keymap_sha256", "keymap.generated.h"),
                              ("hall_defaults_sha256", "hall.generated.h"), ("rgb_layout_sha256", "rgb.generated.h")):
            self.assertEqual(hashlib.sha256((self.root / filename).read_bytes()).hexdigest(), COMPAT[key], filename)

    def test_renaming_fn_cannot_move_it_or_change_its_default_action(self):
        generate_board(ROOT, self.root)
        expected = (self.root / "keymap.generated.h").read_bytes()
        board = copy.deepcopy(load_board())
        next(k for k in board["keys"] if k["raw_slot"] == board["roles"]["fn"])["name"] = "renamed display label"
        folder = self.root / "firmware/board"
        folder.mkdir(parents=True)
        (folder / "bat68.json").write_text(json.dumps(board), encoding="utf-8")
        (folder / "keymap_overrides.json").write_bytes((ROOT / "firmware/board/keymap_overrides.json").read_bytes())
        generate_board(self.root, self.root)
        self.assertEqual((self.root / "keymap.generated.h").read_bytes(), expected)

    def test_accidental_coordinate_changes_are_rejected(self):
        board = copy.deepcopy(load_board())
        board["keys"][0]["matrix"] = [0, 2]
        path = self.root / "board.json"
        path.write_text(json.dumps(board), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ABI digest"):
            load_board(path)

    def test_qmk_metadata_includes_literal_dimensions_and_detects_stale_copies(self):
        sync_keyboard_definition(self.root)
        config = self.root / "keyboards/battle68/config.h"
        self.assertIn("#define MATRIX_ROWS 6\n#define MATRIX_COLS 16\n", config.read_text(encoding="utf-8"))
        sync_keyboard_definition(self.root, check=True)
        config.write_text("#define MATRIX_ROWS 5\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "metadata is stale"):
            sync_keyboard_definition(self.root, check=True)

    def test_storage_schema_matches_installed_firmware(self):
        self.assertEqual(list(map(hex, LAYOUT.eeprom_banks)), COMPAT["eeprom_banks"])
        self.assertEqual(LAYOUT.eeprom_size, COMPAT["eeprom_size"])
        self.assertEqual(LAYOUT.eeprom_version, COMPAT["eeprom_version"])
        self.assertEqual(LAYOUT.via_eeprom_date, COMPAT["via_eeprom_date"])
        self.assertEqual(LAYOUT.eeprom_base, COMPAT["he_base"])
        for name in ("calibration_offset", "profiles_offset", "profile_size", "curve_offset", "controller_offset", "size"):
            self.assertEqual(LAYOUT.he[name], COMPAT["he_" + name])

    def test_real_v36_bank_parses_and_corruption_is_rejected(self):
        banks = (FIXTURES / "bat68_v36_eeprom.bin").read_bytes()
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
        self.assertEqual(normalize_via_tag(payload),bytes.fromhex("261031"))
        self.assertEqual(payload[at:at+3],LAYOUT.via_magic)
        payload[at:at+3]=bytes.fromhex("ffffff")
        with self.assertRaisesRegex(ValueError,"marked for reset"):
            normalize_via_tag(payload)


if __name__ == "__main__":
    unittest.main()
