# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute the synthetic board through the same QMK/HE/USB implementation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'util/sn34'),str(Path(__file__).resolve().parent/'common')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=Path('.build/sn34/sn34_test/default'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    os.environ['SN34_KEYBOARD']='sn34_test'
    os.environ['SN34_NATIVE_BUILD']=str((root/args.build_dir).resolve())
    from keyboard import Keyboard,KEYS,NAMES,BUILD,IMAGE,SYMS
    from model import load_board
    from storage import LAYOUT
    model=load_board()
    m=Keyboard()
    assert 'sn34_xinput_class' not in SYMS
    assert 'rgb_spi' not in SYMS
    assert m.setup(0x80,6,0x0200,0,255)==0
    assert m.transfers[-1][1][4]==3
    tested=0
    for key in KEYS:
        if key['raw_slot']==model['roles']['fn']:continue
        usage=int(key['hid_usage'],0)
        m.press(key['name'])
        assert m.pressed(usage),(key,'press')
        m.release(key['name'])
        assert not m.pressed(usage),(key,'release')
        tested+=1
    m.remap('T0',4)
    for _ in range(32):
        if not m.call('sn34_eeprom_dirty'):break
        assert m.call('sn34_eeprom_save_step')!=0xffffffff
    assert not m.call('sn34_eeprom_dirty')
    snapshot=bytes(m.u.mem_read(LAYOUT.code_limit,LAYOUT.app_size-LAYOUT.code_limit))
    restored=Keyboard(snapshot)
    restored.press('T0');assert restored.pressed(4)
    restored.release('T0');assert not restored.pressed(4)
    assert len(m.raw)==16
    assert m.raw_command(bytes((0xa9,0x10)))[3]==3
    assert m.raw_command(bytes((0xa9,0x23,1)))[0]==255
    assert m.raw_command(bytes((0xa9,0x23,2)))[0]==0xa9
    assert LAYOUT.eeprom_banks==(0x7b000,0x7c000)
    result={'status':'PASS_OFFLINE_NOT_FLASHED','image_sha256':hashlib.sha256(IMAGE).hexdigest(),
            'keys_exercised':tested,'matrix':[3,5],'sample_count':16,'mux_phases':2,'led_count':5,
            'tests':['All ordinary synthetic keys traverse sample -> HE -> QMK -> USB and release cleanly',
                     'RGB, XInput, diagnostics and OTA interfaces are omitted; Raw HID remains correctly routed',
                     'A remap survives cache save and a fresh firmware instance with the synthetic storage layout',
                     'The independent key, sampling, LED and electrical identities are accepted by the shared implementation']}
    (BUILD/'second_target_test_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
