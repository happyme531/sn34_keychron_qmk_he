"""Cross-target contracts with deliberately different geometry and wiring."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"common"))
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'util/sn34'))
import copy
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from build_config import ROOT, BuildPaths
from board import generate_board
from model import load_board
from storage import load_storage


class MultipleTargets(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'keyboards/sn34_test/board'

    def test_second_geometry_and_electrical_ids_do_not_inherit_battle68(self):
        board=load_board(self.folder/'board.json')
        self.assertEqual((board['matrix']['rows'],board['matrix']['cols']),(3,5))
        self.assertEqual(board['scan']['sample_count'],16)
        self.assertEqual(len(board['scan']['phases']),2)
        self.assertTrue(all(k['electrical']>=500 for k in board['keys']))
        self.assertNotEqual(board['leds']['count'],len(board['keys']))
        with TemporaryDirectory(dir=ROOT/'.build') as directory:
            output=Path(directory)
            generate_board(ROOT,output,self.folder/'board.json')
            config=(output/'board_config.generated.h').read_text(encoding='utf-8')
            self.assertIn('#define MATRIX_COLS 5',config)
            self.assertIn('#define SN34_SAMPLE_COUNT 16',config)
            self.assertIn('#define RGB_MATRIX_LED_COUNT 5',config)
            self.assertIn('case 1:',(output/'scan.generated.h').read_text(encoding='utf-8'))
            self.assertNotIn('case 2:',(output/'scan.generated.h').read_text(encoding='utf-8'))

    def test_storage_contract_is_selected_per_board(self):
        first=load_storage(ROOT/'keyboards/battle68/board/storage.json')
        second=load_storage(self.folder/'storage.json')
        self.assertNotEqual(first.eeprom_banks,second.eeprom_banks)
        self.assertNotEqual(first.he['profile_size'],second.he['profile_size'])

    def test_default_build_outputs_do_not_collide(self):
        with patch.dict('os.environ',{'SN34_KEYBOARD':'battle68','SN34_KEYMAP':'default'}):
            first=BuildPaths.environment().build
        with patch.dict('os.environ',{'SN34_KEYBOARD':'sn34_test','SN34_KEYMAP':'default'}):
            second=BuildPaths.environment().build
        with patch.dict('os.environ',{'SN34_KEYBOARD':'battle68','SN34_KEYMAP':'minimal'}):
            third=BuildPaths.environment().build
        self.assertEqual(len({first,second,third}),3)

    def test_duplicate_adc_slots_are_rejected(self):
        board=load_board(self.folder/'board.json')
        board['scan']['phases'][1]['samples'][0]['slot']=0
        with TemporaryDirectory(dir=ROOT/'.build') as directory:
            path=Path(directory)/'board.json'
            path.write_text(json.dumps(board),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate scan slot'):
                load_board(path)


if __name__=='__main__':unittest.main()
