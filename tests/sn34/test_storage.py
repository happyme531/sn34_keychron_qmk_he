# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Verify one persistent EEPROM image for QMK, HE profiles, macros and RGB."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"common"))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import hashlib
import json
import struct
from test_bat68 import Keyboard,BUILD,IMAGE,NAMES,KEYS,SCRATCH,SYMS
from target import ROOT
from storage import LAYOUT, read_banks


def main():
    tests=[];m=Keyboard();r,c=NAMES["A"]["matrix"]
    fixture=ROOT/"tests/sn34/boards/battle68/fixtures"
    compatibility=json.loads((fixture/"sn34_v36_compatibility.json").read_text(encoding="utf-8"))
    old=Keyboard((fixture/"sn34_v36_eeprom.bin").read_bytes())
    backup=bytearray(LAYOUT.app_size)
    backup[LAYOUT.code_limit:LAYOUT.eeprom_end]=(fixture/'sn34_v36_eeprom.bin').read_bytes()
    previous=read_banks(backup)[0]['payload']
    converted=previous
    assert bytes(old.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==converted
    expected=compatibility["settings_fixture"]
    assert old.call("dynamic_keymap_get_keycode",0,r,c)==expected["A_keycode"]
    old.call("dynamic_keymap_macro_get_buffer",0,len(expected["macro_0"])+1,SCRATCH)
    assert bytes(old.u.mem_read(SCRATCH,len(expected["macro_0"])+1))==expected["macro_0"].encode()+b"\0"
    assert old.raw_command(bytes((0xa9,0x10)))[2]==expected["profile"]
    assert (old.call("rgb_matrix_get_hue"),old.call("rgb_matrix_get_sat"))==(expected["rgb_hue"],expected["rgb_saturation"])
    assert old.saved_sequence()==expected["sequence"]
    old.call('sn34_eeprom_save_step')
    interrupted=Keyboard(bytes(old.u.mem_read(0x79000,0x5000)))
    assert bytes(interrupted.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==converted
    old.save()
    migrated=Keyboard(bytes(old.u.mem_read(0x79000,0x5000)))
    assert migrated.call('sn34_eeprom_version')==3
    assert migrated.call('dynamic_keymap_get_keycode',0,r,c)==expected['A_keycode']
    assert migrated.raw_command(bytes((0xa9,0x10)))[2]==expected['profile']
    assert not migrated.call('sn34_eeprom_dirty')
    for key in KEYS:
        row,col=key['matrix'];at=LAYOUT.eeprom_base+LAYOUT.he['calibration_offset']+(row*16+col)*3
        packed=int.from_bytes(previous[at:at+3],'little')
        reply=migrated.raw_command(bytes((0xa9,0x42,row,col)))
        assert struct.unpack_from('<HH',reply,5)==(packed&0xfff,packed>>12),(key['name'],reply.hex())
    tests.append("All v1 cache bytes and all 67 calibration endpoints survive unchanged; interrupted version-only commits replay safely into v3")
    v2_fixture=(fixture/'sn34_v2_eeprom.bin').read_bytes()
    assert hashlib.sha256(v2_fixture).hexdigest()==json.loads((fixture/'sn34_v2_eeprom.json').read_text())['sha256']
    legacy_v2=Keyboard(v2_fixture)
    v2_image=bytearray(LAYOUT.app_size)
    v2_image[LAYOUT.code_limit:LAYOUT.eeprom_end]=(fixture/'sn34_v2_eeprom.bin').read_bytes()
    v2=max(read_banks(v2_image),key=lambda record:record['sequence'])['payload']
    start=LAYOUT.eeprom_base+1
    expected_v3=v2[:start+1]+v2[start:-1]
    assert bytes(legacy_v2.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==expected_v3
    legacy_v2.call('eeprom_update_byte',LAYOUT.eeprom_size-1,1)
    before=bytes(legacy_v2.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))
    assert not legacy_v2.call('sn34_eeprom_migrate')
    assert bytes(legacy_v2.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==before
    assert not legacy_v2.flash
    legacy_v2.call('eeprom_update_byte',LAYOUT.eeprom_size-1,0)
    legacy_v2.call('sn34_eeprom_save_step')
    again=Keyboard(bytes(legacy_v2.u.mem_read(0x79000,0x5000)))
    assert bytes(again.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==expected_v3
    legacy_v2.save()
    again=Keyboard(bytes(legacy_v2.u.mem_read(0x79000,0x5000)))
    assert again.call('sn34_eeprom_version')==3
    assert bytes(again.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))==expected_v3
    tests.append("A real v2 bank migrates calibration/VIA bytes once, survives an interrupted save and reboots as v3")
    fn_before=m.raw_command(bytes((0xa9,0x42,0,0)))[5:9]
    for profile in (1,2,0):
        assert m.raw_command(bytes((0xa9,0x11,profile)))[2]==0
        assert m.raw_command(bytes((0xa9,0x42,0,0)))[5:9]==fn_before
    m.save()
    fn_reloaded=Keyboard(bytes(m.u.mem_read(0x79000,0x5000)))
    assert fn_reloaded.raw_command(bytes((0xa9,0x42,0,0)))[5:9]==fn_before
    tests.append("Profile switching never alters Fn calibration, including cache commit and reboot")
    m=Keyboard()
    m.remap("A",5)
    m.u.mem_write(SCRATCH,b"test\0");m.call("dynamic_keymap_macro_set_buffer",0,5,SCRATCH)
    assert m.raw_command(bytes((0xa9,0x14,1,2,10,3,5,1)))[2]==0
    assert m.raw_command(bytes((0xa9,0x1f,1)))[2]==0
    assert m.raw_command(bytes((0xa9,0x11,1)))[2]==0
    assert m.raw_command(bytes((7,3,2,1)))[0]==7
    assert m.raw_command(bytes((7,3,4,77,88)))[0]==7
    assert m.raw_command(bytes((9,3)))[0]==9
    m.step();m.step(1600)
    assert not m.flash,"Background save must wait until five seconds without key activity"
    m.step(5000)
    assert len(m.flash)<=1,"At most one Flash page can block a main-loop iteration"
    for _ in range(20):m.step(10)
    assert m.flash[-1]==0x7ae00 and set(m.flash)<=set(range(0x79000,0x7b000,512)),m.flash
    flash=bytes(m.u.mem_read(0x79000,0x5000))
    loaded=Keyboard(flash)
    assert loaded.call("dynamic_keymap_get_keycode",0,r,c)==5
    loaded.call("dynamic_keymap_macro_get_buffer",0,5,SCRATCH)
    assert bytes(loaded.u.mem_read(SCRATCH,5))==b"test\0"
    assert loaded.raw_command(bytes((0xa9,0x10)))[2]==1
    loaded.u.mem_write(SCRATCH,bytes(32))
    # The active profile raw buffer begins with its global four-byte config.
    reply=loaded.raw_command(bytes((0xa9,0x12,1,0,0,4)))
    global_raw=int.from_bytes(reply[6:10],"little")
    assert global_raw&3==2 and (global_raw>>2)&63==10,reply.hex()
    hue,sat=loaded.call("rgb_matrix_get_hue"),loaded.call("rgb_matrix_get_sat")
    assert (hue,sat)==(77,88),(hue,sat,bytes(loaded.u.mem_read(SYMS["rgb_matrix_config"],8)).hex())
    assert loaded.saved_sequence()==1
    tests.append("One committed EEPROM image restores dynamic keymaps, macros, selected HE profile, profile thresholds and RGB settings after fresh startup")
    before=len(loaded.flash);assert loaded.save()==0 and len(loaded.flash)==before
    tests.append("No-op save performs no erase/program when the unified settings have not changed")
    partial=Keyboard(flash);partial.remap("A",6)
    partial.call("sn34_eeprom_save_step")
    interrupted=Keyboard(bytes(partial.u.mem_read(0x79000,0x5000)))
    assert interrupted.call("dynamic_keymap_get_keycode",0,r,c)==5
    sr,sc=NAMES["S"]["matrix"];partial.remap("S",7)
    for _ in range(24):partial.call("sn34_eeprom_save_step")
    restored=Keyboard(bytes(partial.u.mem_read(0x79000,0x5000)))
    assert restored.call("dynamic_keymap_get_keycode",0,r,c)==6
    assert restored.call("dynamic_keymap_get_keycode",0,sr,sc)==7
    assert restored.saved_sequence()==2
    tests.append("Interrupted background staging reloads the prior commit; a cache revision during staging restarts and commits both new keymaps consistently")
    erased=Keyboard(flash);erased.remap("A",6)
    erased.call("sn34_eeprom_save_step")
    revision=int.from_bytes(erased.u.mem_read(SYMS["sn34_eeprom_revision"],4),"little")
    erased.call("nvm_eeconfig_erase")
    erased.call("eeprom_read_block",SCRATCH,0,7680)
    assert bytes(erased.u.mem_read(SCRATCH,7680))==bytes(7680)
    assert int.from_bytes(erased.u.mem_read(SYMS["sn34_eeprom_revision"],4),"little")>revision
    erased.save()
    erase_loaded=Keyboard(bytes(erased.u.mem_read(0x79000,0x5000)))
    assert erase_loaded.call("dynamic_keymap_get_keycode",0,r,c)==4
    tests.append("QMK's EEPROM driver erase clears the unified cache and cancels an older staged commit; reboot initializes defaults")
    jitter=Keyboard(flash);jitter.remap("S",9)
    for _ in range(40):
        jitter.travel("A",12);jitter.step(100)
        assert not jitter.pressed(5)
        jitter.release("A");jitter.step(100)
    assert jitter.saved_sequence()==2
    jitter_loaded=Keyboard(bytes(jitter.u.mem_read(0x79000,0x5000)))
    assert jitter_loaded.call("dynamic_keymap_get_keycode",0,sr,sc)==9
    tests.append("Unactuated Hall fluctuations do not starve idle persistence")
    active=Keyboard(flash);active.remap("S",9);active.press("A");active.step(6000)
    assert not active.flash,"A physically actuated key must stop background persistence"
    active.release("A");active.step(4998)
    assert not active.flash,"A complete quiet interval must follow release"
    active.step(5)
    for _ in range(20):active.step(10)
    assert active.saved_sequence()==2
    tests.append("Background persistence waits for actual key release and a complete five-second quiet interval")
    automatic=Keyboard();r,c=NAMES["A"]["matrix"]
    for _ in range(2):
        automatic.travel("A",240);automatic.step();automatic.release("A")
        for _ in range(10):automatic.step()
    values=automatic.raw_command(bytes((0xa9,0x42,r,c)))
    assert struct.unpack_from("<H",values,7)[0]==1680,values.hex()
    tests.append("Automatic full-travel calibration converges on BAT68's measured-scale ADC range instead of requiring Keychron's larger hardcoded range")
    # Real manual calibration command and state machine collect zero samples,
    # enter the bottom phase, then save explicitly without faking completion.
    fresh=Keyboard()
    assert fresh.raw_command(bytes((0xa9,0x40,2)))[2]==0
    for _ in range(10):fresh.step()
    state=fresh.raw_command(bytes((0xa9,0x41)))
    assert state[3]==3,state.hex() # full-travel manual calibration phase
    assert fresh.raw_command(bytes((0xa9,0x40,4)))[2]==0
    fresh.step();assert fresh.raw_command(bytes((0xa9,0x41)))[3]==0
    tests.append("Manual calibration command collects real scan samples, enters the full-travel phase and exits through its save state")
    result=dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
        limits=["Flash pages modeled in this integration test; real Flash HAL is verified separately", "Measured per-key bottom displacement and physical power cycles remain hardware work"])
    (BUILD/"storage_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
