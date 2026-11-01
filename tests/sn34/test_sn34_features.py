# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Exercise user-configurable HE modes and QMK features on the full platform."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import json
import hashlib
import struct
from test_bat68 import Keyboard,NAMES,BUILD,IMAGE,SCRATCH,SYMS


def contains(report,usage):return bool(report[2+usage//8]&(1<<(usage%8)))


def main():
    tests=[];m=Keyboard()
    # Exercise the real matrix/QMK lifecycle, not a direct profile_select call.
    # The user's Win key is Tri Layer Lower; physical Fn remains Right GUI.
    m.remap("Fn",0xe3);m.remap("Win",0x7c77)
    m.press("P");m.press("X");assert m.call("profile_get_current_index")==0
    m.release("X");m.release("P")
    m.press("Win");m.press("X");assert m.call("profile_get_current_index")==0
    m.release("X");m.press("P")
    for name,index in (("X",1),("C",2),("Z",0)):
        m.press(name);assert m.call("profile_get_current_index")==index,(name,index)
        m.release(name)
    m.release("P");m.release("Win");m.step()
    assert m.u.mem_read(SYMS["layer_state"],1)==b"\0" and not any(m.reports()[-1][1:])
    assert m.call("dynamic_keymap_get_keycode",0,*NAMES["Fn"]["matrix"])==0xe3
    # Same-frame presses must work even when remapped Fn is in the last row.
    for name in ("Win","P","X"):m.travel_key(NAMES[name],140)
    m.step();assert m.call("profile_get_current_index")==1
    for name in ("Win","P","X"):m.travel_key(NAMES[name],0)
    m.step();m.step();m.press("A");assert m.pressed(4);m.release("A");assert not m.pressed(4)
    tests.append("Remapped Tri Layer Fn+P+Z/X/C selects all three HE profiles, including simultaneous presses; partial chords do not switch and all releases clear")
    m=Keyboard();m.press("Fn");m.press("P");m.press("C")
    assert m.call("profile_get_current_index")==2
    m.release("C");m.release("P");m.release("Fn");m.step()
    assert m.call("sn34_eeprom_save")>0
    restored=Keyboard(bytes(m.u.mem_read(0x79000,0x5000)))
    assert restored.call("profile_get_current_index")==2
    m=Keyboard();m.call("default_layer_set",4)
    m.press("Fn");m.press("P");m.press("X");assert m.call("profile_get_current_index")==1
    m.release("X");m.release("P");m.release("Fn");m.step()
    assert m.u.mem_read(SYMS["layer_state"],1)==b"\0" and not any(m.reports()[-1][1:])
    tests.append("Ordinary Win/Mac Fn layers support the same profile chord and selected profile survives actual EEPROM save/reload")
    m=Keyboard()
    m.remap("A",0x4104);m.step(250)
    start=len(m.transfers);m.press("A");m.release("A");assert any(contains(p,4) for p in m.reports(start))
    m.step(250);m.press("A");m.step(210);m.press("W");assert m.pressed(0x52)
    m.release("A");m.release("W");assert not m.pressed(0x52)
    tests.append("Layer-Tap tap A, hold layer 1, Fn-layer W and layer-release action cache")
    m=Keyboard();m.remap("A",0x52a2) # OSM(MOD_LSFT)
    m.press("A");m.release("A");m.press("W");assert m.pressed(0xe1) and m.pressed(0x1a)
    m.release("W");m.press("W");assert not m.pressed(0xe1);m.release("W")
    m=Keyboard();m.remap("A",0x5281) # OSL(1)
    m.press("A");m.release("A");start=len(m.transfers);m.press("W")
    # This pinned QMK version synthesizes release before leaving the one-shot
    # layer. Assert the current window's complete tap rather than held state.
    assert any(contains(p,0x52) for p in m.reports(start)) and not m.pressed(0x52)
    m.release("W");m.press("W");assert m.pressed(0x1a) and not m.pressed(0x52);m.release("W")
    tests.append("One-shot Shift and layer apply to one following key and then clear")
    m=Keyboard();m.remap("A",0xa9)
    start=len(m.transfers);m.press("A");m.release("A")
    extra=[p for ep,p in m.transfers[start:] if ep==0x82 and p[0]==4]
    assert extra==[bytes((4,0xe9,0)),bytes((4,0,0))],[p.hex() for p in extra]
    tests.append("Consumer volume-up emits matching press and release on the advertised shared HID report")
    m=Keyboard();names=("Q","W","E","R","T","Y","U","I","O","P")
    for name in names:m.travel_key(NAMES[name],140)
    m.step()
    assert all(m.pressed(int(NAMES[name]["hid_usage"],0)) for name in names)
    for name in names:m.travel_key(NAMES[name],0)
    m.step();assert not any(m.reports()[-1][1:])
    tests.append("Ten simultaneous keys and their releases are represented in NKRO")
    m=Keyboard();m.remap("A",0x7700)
    m.u.mem_write(SCRATCH,b"ab\0");m.call("dynamic_keymap_macro_set_buffer",0,3,SCRATCH)
    start=len(m.transfers);m.press("A");m.release("A")
    reports=m.reports(start)
    assert any(contains(p,4) for p in reports) and any(contains(p,5) for p in reports),[p.hex() for p in reports]
    assert not any(reports[-1][1:])
    tests.append("Dynamic VIA macro sends A and B with real press/release reports in one QMK iteration")
    m=Keyboard();m.remap("A",0x5700)
    start=len(m.transfers);m.press("A");m.release("A");m.step(210)
    assert any(contains(p,0x29) for p in m.reports(start))
    m.step(250);start=len(m.transfers);m.press("A");m.release("A");m.press("A");m.release("A");m.step(210)
    assert any(contains(p,0x39) for p in m.reports(start))
    tests.append("Tap Dance single Escape and double CapsLock run via upstream quantum_task timers")
    m=Keyboard();m.remap("A",0x72);m.remap("S",0x73)
    start=len(m.transfers);m.press("A");m.press("S");m.step(60)
    assert m.pressed(0x39);m.release("A");m.release("S");assert not m.pressed(0x39)
    tests.append("Optional F23+F24 Combo uses the actual QMK combo state machine")
    # Keychron advanced mode payload: profile, mode, row, col, config index.
    m=Keyboard();r,c=NAMES["A"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,3,r,c,0)))[2]==0
    m.press("A");assert m.pressed(4);m.release("A");assert m.pressed(4)
    m.press("A");m.release("A");assert not m.pressed(4)
    tests.append("HE Toggle holds across release and clears on a second actuation")
    m=Keyboard();r1,c1=NAMES["A"]["matrix"];r2,c2=NAMES["D"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x16,0,r1,c1,r2,c2,0,6)))[2]==0
    m.press("A");assert m.pressed(4)
    m.press("D");assert not m.pressed(4) and not m.pressed(7)
    m.release("D");assert m.pressed(4);m.release("A")
    tests.append("HE SOCD neutral suppresses both directions and restores the still-held direction")
    m=Keyboard();r,c=NAMES["A"]["matrix"]
    # Wire format has four full threshold bytes; the profile stores these as
    # six-bit fields. Actions remain four packed uint16 values on the wire.
    cfg=bytes((10,8,25,22))+struct.pack("<4H",5,6,0,0)+struct.pack("<4H",0x0012,0x1200,0,0)
    assert len(cfg)==20
    assert m.raw_command(bytes((0xa9,0x15,0,1,r,c,0))+cfg)[2]==0
    m.travel("A",80);assert m.pressed(5)
    assert not m.pressed(4),"DKS must not send the ordinary A key as well"
    m.travel("A",180);assert m.pressed(6)
    m.travel("A",190);m.travel("A",120);assert not m.pressed(6)
    m.release("A");assert not m.pressed(5)
    tests.append("HE DKS shallow/deep actions emit B/C press/release reports through the FIFO")
    m=Keyboard();r,c=NAMES["W"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,3)))[2]==0 # up is negative HID Y
    start=len(m.transfers);m.travel("W",160);m.travel("W",200)
    js=[p for ep,p in m.transfers[start:] if ep==0x82 and p[0]==7]
    assert js and struct.unpack("b",js[-1][2:3])[0]<0,[p.hex() for p in js]
    assert not m.pressed(0x1a),"Gamepad-only mode must not also send keyboard W"
    m.release("W");assert [p for ep,p in m.transfers if ep==0x82 and p[0]==7][-1][2]==0
    tests.append("HE analog joystick Y axis emits the advertised gamepad report and returns to center")
    m=Keyboard();r,c=NAMES["A"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,13)))[2]==0 # gamepad button 0
    start=len(m.transfers);m.press("A")
    js=[p for ep,p in m.transfers[start:] if ep==0x82 and p[0]==7]
    assert js and js[-1][7]&1,[p.hex() for p in js]
    m.release("A");assert not [p for ep,p in m.transfers if ep==0x82 and p[0]==7][-1][7]&1
    tests.append("HE gamepad button indices map to actual HID buttons, with matching release")
    m=Keyboard()
    assert m.raw_command(bytes((0xa9,0x23,1)))[0]==0xa9
    r,c=NAMES["W"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,3)))[2]==0
    start=len(m.transfers);m.travel("W",160);m.travel("W",200)
    x=[p for ep,p in m.transfers[start:] if ep==0x86]
    assert x and x[-1][:2]==bytes((0,20)) and struct.unpack_from("<h",x[-1],8)[0]>0,[p.hex() for p in x]
    m.release("W");assert struct.unpack_from("<h",[p for ep,p in m.transfers if ep==0x86][-1],8)[0]==0
    r,c=NAMES["A"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,13)))[2]==0
    m.press("A");assert struct.unpack_from("<H",[p for ep,p in m.transfers if ep==0x86][-1],2)[0]&(1<<12)
    m.release("A");assert not struct.unpack_from("<H",[p for ep,p in m.transfers if ep==0x86][-1],2)[0]
    tests.append("Keychron XInput thumbstick and A button produce exact 20-byte XUSB packets on the vendor endpoint")
    result=dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
        limits=["Hardware USB/ADC and Flash page effects modeled", "Windows XInput driver binding and physical lighting order require hardware validation"])
    (BUILD/"feature_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
