"""Check the Battle68 matrix, defaults and storage bounds."""
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
from storage import load_storage, STORAGE_FILE

FIXTURES = ROOT / "tests/sn34/boards/battle68/fixtures"
CONTRACT = json.loads((FIXTURES / "board_contract.json").read_text(encoding="utf-8"))


class BoardContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="contract-test-", dir=ROOT / ".build")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_matrix_identity_matches_the_frozen_contract(self):
        board = load_board()
        self.assertEqual(matrix_digest(board["keys"]), CONTRACT["matrix_sha256"])
        table=(ROOT/'keyboards/battle68/board/keys.inc').read_text(encoding='utf-8')
        actual=[{'raw_slot':int(raw),'matrix':[int(slot)//board['matrix']['cols'],int(slot)%board['matrix']['cols']]}
                for raw,slot,idle,bottom in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}',table)]
        self.assertEqual(matrix_digest(actual), CONTRACT['matrix_sha256'])
        fn = next(k for k in board["keys"] if k["raw_slot"] == board["roles"]["fn"])
        self.assertEqual(fn["matrix"], [0, 0])
        definition = keyboard_definition()
        self.assertEqual({tuple(k["matrix"]) for k in definition["layouts"]["LAYOUT"]["layout"]},
                         {tuple(k["matrix"]) for k in board["keys"]})

    def test_default_keymap_calibration_and_led_tables_are_unchanged(self):
        digest = lambda value: hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()
        keymap = (ROOT/'keyboards/battle68/keymaps/default/keymap.c').read_text(encoding='utf-8')
        values = re.sub(r'\s+', '', keymap.split('=', 1)[1].split(';',1)[0])
        self.assertEqual(digest(values), CONTRACT['default_keymap_values_sha256'])
        table = (ROOT / 'keyboards/battle68/board/keys.inc').read_text(encoding='utf-8')
        hall = [[int(row.split(',')[i]) for i in (1, 2, 3)]
                for row in re.findall(r'\{(\d+,\d+,\d+,\d+)\}', table)]
        self.assertEqual(digest(hall), CONTRACT['hall_defaults_values_sha256'])
        board=load_board()
        leds=keyboard_definition()['rgb_matrix']['layout']
        matrix=[[255]*board['matrix']['cols'] for _ in range(board['matrix']['rows'])]
        for index,led in enumerate(leds):
            if 'matrix' in led:
                row,col=led['matrix'];matrix[row][col]=index
        values=[matrix,[[led['x'],led['y']] for led in leds],[led['flags'] for led in leds]]
        self.assertEqual(digest(values), CONTRACT['rgb_layout_values_sha256'])

    def test_invalid_storage_regions_are_rejected(self):
        for changes in ({"page_size": 0}, {"eeprom_banks": ["0x79000", "0x79000"]}, {"footer_address": "0x79000"}):
            data = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
            data.update(changes)
            path = self.root / "storage.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_storage(path)


if __name__ == "__main__":
    unittest.main()
