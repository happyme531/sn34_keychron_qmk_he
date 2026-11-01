# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute production QMK keyboard_task, HE core, USB FIFO and raw HID."""
import os
os.environ.setdefault("BAT68_NATIVE_BUILD","build/bat68")
import hashlib
import json
import struct
from test_native_usb import Machine,ROOT,BUILD,SYMS,IMAGE,SCRATCH
from bat68_model import load_board
from unicorn import UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR

KEYS=json.loads((BUILD/"board.json").read_text())
PROFILES={k["raw_slot"]:{**k,"idle":k["hall"]["released"],"pressed":k["hall"]["bottom"]} for k in load_board()["keys"]}
NAMES={k["name"]:k for k in KEYS}
CURVE_STEPS=json.loads((ROOT/"firmware/board/hall_curve.json").read_text(encoding="utf-8"))["adc_step_counts"]


class Keyboard(Machine):
    def __init__(self,flash=None,real_usb_endpoints=False,configure=True):
        self.real_usb_endpoints=real_usb_endpoints
        self.tick=0;self.complete=True;self.flash=[];self.spi=[];self.spi_done=0;self.rx_lengths={};self.usb_link=[]
        super().__init__()
        if real_usb_endpoints:
            for name in ("HAL_PCD_EP_Open","HAL_PCD_EP_Close"):self.stub_addresses.pop(SYMS[name]&~1,None)
        self.u.mem_map(0xe000e000,0x2000)
        self.u.mem_map(0xe0001000,0x1000)
        self.u.mem_write(0xe000ed88,(0xf<<20).to_bytes(4,"little"))
        self.u.mem_map(0x79000,0x5000,UC_PROT_READ|UC_PROT_EXEC)
        self.u.mem_write(0x79000,bytes(0x5000))
        if flash is not None:self.u.mem_write(0x79000,flash)
        self.raw=[2300]*96
        for p in PROFILES.values():self.raw[p["raw_slot"]]=p["idle"]
        self.frame=0
        self.call("protocol_setup");self.call("keyboard_setup");self.call("protocol_pre_init")
        self.call("keyboard_init");self.call("protocol_post_init")
        self.call("USBD_Reset",SYMS["device"])
        if configure:assert self.setup(0,5,7)==0 and self.setup(0,9,1)==0
        for _ in range(12):self.step()

    def on_code(self,u,address,size,data):
        if self.real_usb_endpoints and address==(SYMS.get("otgpe_ep_fifo_reset",1)&~1):
            # Hardware clears the FIFO reset bit by itself. Keep the real HAL
            # close and allocator release, modeling only this register effect.
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        for name in ("HAL_PCD_Start","HAL_PCD_Stop","HAL_PCD_ForceFullSpeed"):
            if address==(SYMS.get(name,1)&~1):
                self.usb_link.append((name,u.reg_read(UC_ARM_REG_R1),self.tick))
                u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if self.real_usb_endpoints and address==(SYMS["HAL_PCD_EP_Open"]&~1):
            from unicorn.arm_const import UC_ARM_REG_R2,UC_ARM_REG_R3
            self.endpoints.append((u.reg_read(UC_ARM_REG_R1),u.reg_read(UC_ARM_REG_R2),u.reg_read(UC_ARM_REG_R3)))
            return # Execute the real HAL and FIFO allocator against modeled registers.
        if address==(SYMS.get("HAL_PCD_EP_GetStatus",1)&~1):
            u.reg_write(UC_ARM_REG_R0,1 if u.reg_read(UC_ARM_REG_R1)==5 else 0)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if address==(SYMS.get("HAL_PCD_EP_GetRxCount",1)&~1):
            u.reg_write(UC_ARM_REG_R0,self.rx_lengths.get(u.reg_read(UC_ARM_REG_R1),0))
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if address==(SYMS["HAL_GetTick"]&~1):
            u.reg_write(UC_ARM_REG_R0,self.tick);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if address==(SYMS["HAL_Delay"]&~1):self.tick+=u.reg_read(UC_ARM_REG_R0)
        if address==(SYMS.get("HAL_IWDG_Refresh",1)&~1):
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if address==(SYMS.get("HAL_SPI_Transmit_DMA",1)&~1):
            from unicorn.arm_const import UC_ARM_REG_R2
            self.spi.append(bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),u.reg_read(UC_ARM_REG_R2))))
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if address==(SYMS["sn34_flash_write_eeprom_page"]&~1):
            at=u.reg_read(UC_ARM_REG_R0);assert 0x79000<=at<0x7d000 and at%512==0
            self.flash.append(at);u.mem_write(at,bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),512)))
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        super().on_code(u,address,size,data)

    def step(self,ms=1):
        self.tick+=ms;self.frame+=1
        self.u.mem_write(SYMS["completed_raw"],struct.pack("<96H",*self.raw))
        self.u.mem_write(SYMS["native_raw"],struct.pack("<96H",*self.raw))
        self.u.mem_write(SYMS["native_scan_frames"],struct.pack("<I",self.frame))
        for task in ("protocol_pre_task","protocol_keyboard_task","protocol_post_task","raw_hid_task","housekeeping_task"):self.call(task)
        if self.complete:
            self.drain()
            if self.spi_done<len(self.spi):
                self.call("HAL_SPI_TxCpltCallback",SYMS["rgb_spi"]);self.spi_done=len(self.spi)

    def drain(self):
        for _ in range(300):
            for ep in (0x81,0x82,0x83,0x85,0x86):self.call("HAL_PCD_DataInStageCallback",0,ep)
            before=len(self.transfers);self.call("bat68_host_task")
            if len(self.transfers)==before:break

    def travel_key(self,key,travel):
        p=PROFILES[key["raw_slot"]]
        # Physical stimuli follow the stock ADC response; requested travel is
        # uniform displacement, rather than a linear change in magnetic ADC.
        position=max(0,min(240,travel))*len(CURVE_STEPS)
        index,fraction=divmod(position,240)
        drop=sum(CURVE_STEPS[:index])*240
        if index<len(CURVE_STEPS):drop+=CURVE_STEPS[index]*fraction
        denominator=sum(CURVE_STEPS)*240
        delta=(drop*(p["idle"]-p["pressed"])+denominator//2)//denominator
        self.raw[key["raw_slot"]]=max(0,p["idle"]-delta)

    def travel(self,name,travel):self.travel_key(NAMES[name],travel);self.step()
    def press(self,name):self.travel(name,140)
    def release(self,name):self.travel(name,0)
    def reports(self,start=0):return [p for ep,p in self.transfers[start:] if ep==0x82 and p and p[0]==6]
    def pressed(self,usage):
        reports=self.reports()
        if not reports:return False
        p=reports[-1]
        if 0xe0<=usage<=0xe7:return bool(p[1]&(1<<(usage-0xe0)))
        return bool(p[2+usage//8]&(1<<(usage%8)))

    def remap(self,name,code):
        r,c=NAMES[name]["matrix"];self.call("dynamic_keymap_set_keycode",0,r,c,code)

    def raw_command(self,payload):
        data=payload+bytes(32-len(payload));self.u.mem_write(SCRATCH,data)
        before=len(self.transfers);self.call("bat68_raw_hid_receive",SCRATCH,32);self.drain()
        return [p for ep,p in self.transfers[before:] if ep==0x85][-1]


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
