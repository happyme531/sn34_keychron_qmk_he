# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Exercise input thresholds, persistent mode changes and USB transitions."""
import hashlib
import json
import struct
from test_bat68 import Keyboard, BUILD, IMAGE, NAMES, KEYS, SYMS, SCRATCH


class PollingClock(Keyboard):
    def __init__(self):
        self.poll_clock=False
        super().__init__()
    def on_code(self,u,address,size,data):
        if self.poll_clock and address==(SYMS["HAL_GetTick"]&~1):self.tick+=1
        super().on_code(u,address,size,data)


def usb_state(keyboard):
    # The pinned QMK struct has idle/LED/protocol/configure bytes; both
    # platform builds deliberately use -fshort-enums.
    return keyboard.u.mem_read(SYMS["usb_device_state"]+3,1)[0]


def main():
    tests=[];m=Keyboard()
    for travel,down in ((60,False),(90,True),(64,True),(44,False)):
        m.travel("W",travel);assert m.pressed(0x1a)==down,(travel,m.reports()[-1].hex())
    m.release("W")
    assert m.raw_command(bytes((0xa9,0x11,1)))[2]==0
    for travel,down in ((60,False),(130,True),(180,True),(148,False),(170,False),(182,True),(0,False)):
        m.travel("W",travel);assert m.pressed(0x1a)==down,(travel,m.reports()[-1].hex())
    tests.append("Regular hysteresis and rapid trigger moving extrema run through the production QMK loop")
    a=NAMES["A"]["matrix"];d=NAMES["D"]["matrix"]
    for mode,both in ((3,(False,True)),(4,(True,False)),(5,(False,True)),(6,(False,False))):
        m=Keyboard();assert m.raw_command(bytes((0xa9,0x16,0,*a,*d,0,mode)))[2]==0
        m.press("A");m.press("D");assert (m.pressed(4),m.pressed(7))==both,mode
        m.release("D");assert m.pressed(4);m.release("A");assert not m.pressed(4)
    for mode in (1,2):
        m=Keyboard();assert m.raw_command(bytes((0xa9,0x16,0,*a,*d,0,mode)))[2]==0
        m.travel("A",120);m.travel("D",180);assert not m.pressed(4) and m.pressed(7),mode
        m.travel("A",220);assert m.pressed(4) and not m.pressed(7),mode
        m.release("D");m.release("A")
    tests.append("All six SOCD policies arbitrate opposing keys and release without stuck reports")
    m=Keyboard();m.remap("A",0xd1);m.remap("S",0xd0)
    start=len(m.transfers);m.press("A");m.press("S");m.step(350);m.release("A");m.release("S")
    mouse=[p for ep,p in m.transfers[start:] if ep==0x82 and p[0]==2]
    assert any(p[1]&1 for p in mouse) and any(p[2]>0 for p in mouse),[p.hex() for p in mouse]
    assert not any(mouse[-1][1:]),mouse[-1].hex()
    tests.append("Mouse buttons and repeated cursor movement use the advertised shared report and clear on release")
    m=Keyboard();m.remap("A",0x7e1e);m.press("A");m.release("A")
    m.press("Win");assert not m.pressed(0xe3);m.release("Win")
    m.remap("S",0x7e1f);m.press("S");m.release("S")
    assert int.from_bytes(m.u.mem_read(SYMS["default_layer_state"],1),"little")==4
    m.step();m.call("bat68_eeprom_save")
    loaded=Keyboard(bytes(m.u.mem_read(0x79000,0x5000)))
    assert int.from_bytes(loaded.u.mem_read(SYMS["default_layer_state"],1),"little")==4
    # Unlock from a key on the Mac layer, then verify physical Option/Command.
    r,c=NAMES["A"]["matrix"];loaded.call("dynamic_keymap_set_keycode",2,r,c,0x7e1e)
    loaded.press("A");loaded.release("A");loaded.press("Win");assert loaded.pressed(0xe2);loaded.release("Win")
    alt=next(k for k in KEYS if k["raw_slot"]==82)
    loaded.travel_key(alt,140);loaded.step();assert loaded.pressed(0xe3)
    loaded.travel_key(alt,0);loaded.step()
    tests.append("Win lock and Mac base layer persist together; Mac Option/Command positions match their physical keys")
    m=Keyboard();m.press("A");m.call("HAL_PCD_SuspendCallback",0);m.step()
    assert usb_state(m)==3
    assert m.u.mem_read(SYMS["suspend_state"],1)==b"\x01"
    m.release("A");m.call("HAL_PCD_ResumeCallback",0);m.step();m.step()
    assert usb_state(m)==2
    assert m.u.mem_read(SYMS["suspend_state"],1)==b"\0" and not m.pressed(4)
    m.press("S");assert m.pressed(0x16);m.release("S")
    m.call("USBD_Reset",SYMS["device"]);m.step()
    assert usb_state(m)==1
    assert m.setup(0,5,7)==0 and m.setup(0,9,1)==0;m.step()
    m.press("A");assert m.pressed(4);m.release("A");assert not m.pressed(4)
    tests.append("USB suspend/resume and bus reset synchronize QMK state, RGB suspend, neutral reports and subsequent typing")
    m=PollingClock();m.complete=False;m.press("A")
    m.u.mem_write(SCRATCH,bytes(32));m.poll_clock=True
    for _ in range(270):m.call("host_raw_hid_send",SCRATCH,32)
    assert int.from_bytes(m.u.mem_read(SYMS["bat68_report_overflows"],4),"little")>0
    m.poll_clock=False;m.complete=True;m.drain()
    assert m.call("bat68_host_queued")==0 and m.pressed(4)
    m.release("A");m.press("S");assert m.pressed(0x16);m.release("S")
    tests.append("Raw HID backpressure is bounded and counted without clearing a still-held physical key")
    # Reproduce a stalled configuration endpoint with exactly 160 queued
    # reports. It must neither block the independent keyboard endpoint nor
    # gate keyboard_task before the ADC samples reach HE.
    m=Keyboard();m.complete=False;m.u.mem_write(SCRATCH,bytes(32))
    for _ in range(161):m.call("host_raw_hid_send",SCRATCH,32)
    assert m.call("bat68_host_queued")==160
    assert m.call("bat68_host_ready")==1
    m.press("A");assert m.pressed(4)
    m.call("HAL_PCD_DataInStageCallback",0,0x82);m.release("A");assert not m.pressed(4)
    assert m.call("bat68_host_queued")==160
    assert int.from_bytes(m.u.mem_read(SYMS["bat68_report_overflows"],4),"little")==0
    tests.append("A stalled Raw HID endpoint with 160 pending replies does not suppress ADC processing or keyboard press/release")
    # Axis samples can be replaced, but every gamepad button transition must
    # remain ordered. Only the pending tail with unchanged buttons coalesces.
    m=Keyboard();m.complete=False
    for axis in range(20):
        packet=bytearray(20);packet[1]=20;packet[6]=axis
        m.u.mem_write(SCRATCH,bytes(packet));m.call("host_xinput_send",SCRATCH)
    assert m.call("bat68_host_queued")==1
    assert int.from_bytes(m.u.mem_read(SYMS["bat68_axis_coalesced"],4),"little")==18
    for buttons in (1,0):
        packet[2]=buttons;m.u.mem_write(SCRATCH,bytes(packet));m.call("host_xinput_send",SCRATCH)
    assert m.call("bat68_host_queued")==3
    m.complete=True;m.drain()
    x=[p for ep,p in m.transfers if ep==0x86]
    assert [p[2] for p in x[-3:]]==[0,1,0]
    tests.append("Pending XInput axes coalesce under endpoint backpressure while button press and release remain ordered")
    # Check reloaded interpolation, not just that the control points read back.
    m=Keyboard();curve=bytes((0,0,10,10,30,100,40,127))
    assert m.raw_command(bytes((0xa9,0x21))+curve)[2]==0
    r,c=NAMES["W"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,3)))[2]==0
    assert m.raw_command(bytes((0xa9,0x1f,0)))[2]==0
    m.step();m.call("bat68_eeprom_save");loaded=Keyboard(bytes(m.u.mem_read(0x79000,0x5000)))
    values=[]
    for keyboard in (m,loaded):
        start=len(keyboard.transfers);keyboard.travel("W",150)
        js=[p for ep,p in keyboard.transfers[start:] if ep==0x82 and p[0]==7]
        values.append(struct.unpack("b",js[-1][2:3])[0])
    assert values[0]==values[1] and values[0]<-10,values
    tests.append("Saved custom gamepad response curve produces identical intermediate axis values after fresh startup")
    result=dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
        limits=["USB, ADC input and persistent pages are modeled; no physical suspend-current or host driver claim"])
    (BUILD/"lifecycle_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
