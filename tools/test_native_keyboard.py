# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute Hall -> upstream QMK -> real SDK HID with modeled PCD transfers."""
import hashlib
import json
import struct
from unicorn.arm_const import *
from unicorn import UC_PROT_READ,UC_PROT_EXEC
from test_native_usb import Machine,ROOT,BUILD,SYMS,IMAGE,SCRATCH,MANIFEST

KEYS=json.loads((ROOT/"analysis/hall_board_profile.json").read_text())["keys"]
NAMES={k["name"]:k for k in KEYS}
MAPPING=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]

class Keyboard(Machine):
    def __init__(self):
        self.tick=0
        super().__init__()
        self.u.mem_map(0x7d000,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.u.mem_write(0x7d000,b"\xff"*0x1000)
        if MANIFEST.get("keychron_he"):
            self.u.mem_map(0xe000e000,0x2000)
            self.u.mem_write(0xe000ed88,(0xf<<20).to_bytes(4,"little"))
            self.u.mem_map(0x7b000,0x2000,UC_PROT_READ|UC_PROT_EXEC)
            self.u.mem_write(0x7b000,b"\0"*0x2000)
        self.raw=[2300]*96
        for k in KEYS:self.raw[k["raw_slot"]]=k["idle"]
        assert self.call("native_usb_init")==0
        self.call("USBD_Reset",SYMS["device"])
        assert self.setup(0,5,7)==0 and self.setup(0,9,1)==0
        self.call("native_keyboard_init")
        self.frame=0;self.complete=True
        self.step()
        if MANIFEST.get("keychron_he"):
            for _ in range(10): self.step()
    def on_code(self,u,address,size,data):
        if address==(SYMS["HAL_GetTick"]&~1):
            self.tick+=1
            u.reg_write(UC_ARM_REG_R0,self.tick);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        super().on_code(u,address,size,data)
    def step(self):
        self.frame+=1
        self.u.mem_write(SYMS["native_raw"],struct.pack("<96H",*self.raw))
        self.u.mem_write(SYMS["native_scan_frames"],struct.pack("<I",self.frame))
        self.call("native_keyboard_task")
        if self.complete:self.call("HAL_PCD_DataInStageCallback",0,0x81)
    def set(self,name,travel):
        self.set_key(NAMES[name],travel)
    def set_key(self,k,travel):
        # Choose a raw count whose integer normalized travel is at least target.
        delta=(travel*(k["idle"]-k["pressed"])+329)//330
        self.raw[k["raw_slot"]]=max(0,k["idle"]-delta)
    def press(self,name,travel=150):self.set(name,travel);self.step()
    def release(self,name):self.press(name,0)
    def report(self):return [p for ep,p in self.transfers if ep==0x81][-1]
    def command(self,cmd,count=0,row=0,col=0,value=0,payload=None):
        rx=bytearray(64);rx[:8]=bytes((0xaa,cmd,count,row,col))+b"B68"
        struct.pack_into("<H",rx,8,value)
        if payload:rx[8:8+len(payload)]=payload
        self.u.mem_write(SCRATCH,bytes(rx));self.u.mem_write(SCRATCH+256,bytes(64))
        assert self.call("native_keyboard_command",SCRATCH,SCRATCH+256)==1
        return bytes(self.u.mem_read(SCRATCH+256,64))

def main():
    tests=[];m=Keyboard();assert m.report()==bytes(8)
    for key in MAPPING:
        if key["name"]=="Fn":continue
        profile=next(k for k in KEYS if k["electrical"]==key["electrical"])
        m.set_key(profile,150);m.step();report=m.report();usage=int(key["hid_usage"],0)
        if 0xe0<=usage<=0xe7:assert report[0]&(1<<(usage-0xe0)),(key,report.hex(),m.command(0x74).hex())
        else:assert usage in report[2:],(key,report.hex())
        m.set_key(profile,0);m.step();assert m.report()==bytes(8),(key,"stuck release")
    tests.append("All 66 non-Fn keys from per-key raw ADC through normalized Hall travel, upstream QMK and SDK HID")
    m.press("Fn");m.press("1");assert 0x3a in m.report()[2:]
    m.release("Fn");m.release("1");assert m.report()==bytes(8)
    m.set("Fn",150);m.set("2",150);m.step();assert 0x3b in m.report()[2:]
    m.release("Fn");m.release("2");assert m.report()==bytes(8)
    m.press("Fn");m.press("W");assert 0x52 in m.report()[2:]
    m.release("W");m.release("Fn");assert m.report()==bytes(8)
    tests.append("Fn+1, simultaneous Fn+2, Fn+W and releasing Fn first")
    for travel,pressed in ((98,False),(102,True),(82,True),(76,False)):
        m.press("W",travel);assert (0x1a in m.report()[2:])==pressed,(travel,m.report())
    m.release("W");tests.append("100/80 normalized Hall hysteresis")
    k=NAMES["A"];r,c=divmod(k["raw_slot"],16)
    assert m.command(0x75,0,r,c,5)[8:10]==b"\x05\0"
    assert m.command(0x76,0,r,c)[8:10]==b"\x05\0"
    m.press("A");assert 5 in m.report()[2:]
    assert m.command(0x75,0,r,c,4)[2]==255
    assert m.command(0x79,payload=b"SAVE")[2]==255
    m.release("A");assert m.command(0x75,0,r,c,4)[2]==2
    for args in ((2,0,0),(0,6,0),(0,0,16)):assert m.command(0x75,*args,value=4)[2]==255
    assert m.command(0x79)[2]==255
    tests.append("Live remapping, held-key save/remap guards, invalid coordinates and save signature")
    m.complete=False;m.press("D");before=len(m.transfers);m.release("D")
    assert len(m.transfers)==before
    m.call("HAL_PCD_DataInStageCallback",0,0x81);m.step();assert m.report()==bytes(8)
    m.complete=True;tests.append("Busy SDK keyboard endpoint retries pending release")
    assert m.setup(0xa1,1,0x0100,0,8)==0
    assert m.transfers[-1]==(0x80,bytes(8)),m.transfers[-1]
    tests.append("HID GET_REPORT returns the current eight-byte keyboard report")
    for cmd in (0x71,0x77):
        assert m.command(cmd,24)[2]==48
        for count,offset in ((0,0),(25,0),(2,127)):
            assert m.command(cmd,count,offset&255,offset>>8)[2]==255
    status=m.command(0x74);assert status[12]==(6 if MANIFEST.get("standalone") else 5) and status[17]==status[19]==1
    assert not any(struct.unpack_from("<6H",status,24))
    assert m.command(0x7a)[2]==255
    assert m.command(0x7a,payload=b"REBT")[2]==1
    assert m.u.mem_read(SYMS["native_restart_requested"],1)==b"\x01"
    tests.append("Diagnostic snapshot bounds, native QMK identity, released matrix and restart signature")
    magic=bytes.fromhex("aa55a55aff0033cc")
    m.u.mem_write(SCRATCH,magic)
    for interface,report_id,length in ((2,0,8),(3,1,8),(3,0,7)):
        assert m.call("set_feature",interface,report_id,SCRATCH,length)!=0
        assert m.u.mem_read(SYMS["native_boot_requested"],1)==b"\0"
    assert m.call("set_feature",3,0,SCRATCH,8)==0
    assert m.u.mem_read(SYMS["native_boot_requested"],1)==b"\x01"
    tests.append("OEM OTA feature magic is accepted only on interface 3 and schedules a main-context Bootloader entry")
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),"tests":tests,
            "limits":["Raw ADC and PCD hardware transfers are modeled; physical key travel and host input require hardware tests", "Flash HAL persistence is tested separately"]}
    (BUILD/"keyboard_test_results.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
