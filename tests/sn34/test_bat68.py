# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Battle68 behavior regression on the shared ARM/QMK emulator."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/"util/sn34"),str(Path(__file__).resolve().parent/"common")]
import json,hashlib
from keyboard import Keyboard,KEYS,NAMES,PROFILES,CURVE_STEPS,BUILD,SYMS,IMAGE,SCRATCH

def main():
    tests=[];m=Keyboard()
    # Exercise the freestanding word-copy paths with every relative alignment,
    # short tails and guard bytes. These primitives also serve USB and EEPROM.
    pattern=bytes((i*37+19)&255 for i in range(768))
    for length in (0,1,2,3,4,5,7,8,15,31,64,95,192):
        for source_align in range(4):
            for dest_align in range(4):
                m.u.mem_write(SCRATCH,pattern)
                expected=bytearray(pattern)
                expected[384+dest_align:384+dest_align+length]=pattern[source_align:source_align+length]
                m.call("memcpy",SCRATCH+384+dest_align,SCRATCH+source_align,length)
                assert bytes(m.u.mem_read(SCRATCH,768))==expected,(length,source_align,dest_align)
        for dest_align in range(4):
            m.u.mem_write(SCRATCH,pattern)
            expected=bytearray(pattern);expected[dest_align:dest_align+length]=bytes((0xa7,))*length
            m.call("memset",SCRATCH+dest_align,0xa7,length)
            assert bytes(m.u.mem_read(SCRATCH,768))==expected,(length,dest_align)
    tests.append("Word memory copies/fills preserve every alignment, short tail and surrounding guard byte")
    for key in KEYS:
        if key["name"]=="Fn":continue
        usage=int(key["hid_usage"],0)
        m.travel_key(key,140);m.step();assert m.pressed(usage),(key,m.reports()[-1].hex())
        m.travel_key(key,0);m.step();assert not m.pressed(usage),(key,"stuck")
    tests.append("All 66 keys pass complete-frame ADC -> Keychron HE -> upstream keyboard_task -> NKRO USB")
    for name,usage in (("2",0x3b),("W",0x52)):
        m.travel_key(NAMES["Fn"],140);m.travel_key(NAMES[name],140);m.step();assert m.pressed(usage)
        m.release("Fn");m.release(name);assert not m.pressed(usage)
    tests.append("Fn priority comes from logical matrix ordering; simultaneous Fn+2 and Fn+W use standard QMK dispatch")
    m.remap("A",0x2104);m.step(250)
    start=len(m.transfers);m.press("A");assert not m.pressed(4);m.release("A")
    reports=m.reports(start)
    assert any(p[2]&(1<<4) for p in reports),[p.hex() for p in reports]
    assert not m.pressed(4)
    m.step(250);m.press("A");m.step(210);assert m.pressed(0xe0);m.release("A");assert not m.pressed(0xe0)
    tests.append("Mod-Tap emits a real tap press AND release in the current transfer window; held Ctrl also passes")
    # The same tap under endpoint backpressure must retain both transitions.
    m.step(250);m.complete=False;m.press("D");m.release("D")
    start=len(m.transfers);m.press("A");m.release("A");m.complete=True;m.drain()
    assert any(p[2]&(1<<4) for p in m.reports(start)),[p.hex() for p in m.reports(start)]
    assert not m.pressed(4)
    tests.append("Busy shared endpoint preserves ordered tap press/release instead of replacing the pending report")
    assert m.raw_command(bytes((1,)))[:3]==bytes((1,0,12))
    assert m.raw_command(bytes((0xa9,0x10)))[3]==3
    tests.append("Standard VIA version and original Keychron HE profile-info commands share the dedicated Raw HID interface")
    result=dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
        limits=["ADC samples, physical USB and Flash page effects modeled; real QMK, HE and SDK HID code executes", "RGB, XInput and additional HE modes still need dedicated coverage"])
    (BUILD/"platform_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
