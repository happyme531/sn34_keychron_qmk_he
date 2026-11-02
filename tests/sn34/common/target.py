"""Target selection for the offline firmware tests."""
import json
import os
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[3]

def keyboard_name():
    name=os.environ.get('SN34_KEYBOARD','battle68')
    if not re.fullmatch(r'[a-z0-9_]+(?:/[a-z0-9_]+)*',name):raise ValueError('Invalid keyboard name')
    return name

def board_directory():
    return ROOT/'tests/sn34/boards'/keyboard_name()/'fixtures'

def target_tests(keyboard,keymap):
    target=json.loads((ROOT/'tests/sn34/boards'/keyboard/'fixtures/target.json').read_text(encoding='utf-8'))
    return target.get('keymap_tests',{}).get(keymap,target['tests'])
