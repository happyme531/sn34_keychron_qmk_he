# /// script
# dependencies = ["unicorn", "pyelftools", "pefile"]
# ///
"""Execute the actual Thumb QMK bridge, key engine, layers, and probe hooks."""
from pathlib import Path
import hashlib
import json
import struct
import zlib
from elftools.elf.elffile import ELFFile
import pefile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *
from hardware_registers import REGISTERS

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/"build/qmk_bridge"
IMAGE=(BUILD/"bat68_qmk_bridge_v118.bin").read_bytes()
MANIFEST=json.loads((BUILD/"manifest.json").read_text())
MANIFEST["status"]="TESTING_NOT_FLASHED"
(BUILD/"manifest.json").write_text(json.dumps(MANIFEST,indent=2))
with (BUILD/"bat68_qmk_bridge.elf").open("rb") as f:
    elf=ELFFile(f)
    SYMBOLS={s.name:s.entry.st_value for s in elf.get_section_by_name(".symtab").iter_symbols()}
MAPPING=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
NAMES={k["name"]:k for k in MAPPING}
RAM=0x20000000
STOP=0x100000
RX,TX=0x20003668,0x20003628
NV_PAGES=(0x7d000,0x7d200)
class SimulatedPowerLoss(Exception):pass

class Machine:
    def __init__(self,image=IMAGE):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        self.u.mem_map(0,0x80000,UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(0,image)
        self.u.mem_map(RAM,0x28000,UC_PROT_READ|UC_PROT_WRITE);self.u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.fmc_regs={};self.fmc_fifo=bytearray(512);self.power_loss_triggered=False
        self.fmc_stuck_busy=False;self.fmc_fail_on=None
        self.u.mmio_map(0x00600000,0x2000,self.fmc_read,None,self.fmc_write,None)
        self.remap=True;self.dwt_cycles=0;self.dwt_step=12000;self.core_regs={}
        self.u.mmio_map(0x40000000,0x100000,self.periph_read,None,self.periph_write,None)
        self.u.mmio_map(0xe0000000,0x20000,self.core_read,None,self.core_write,None)
        self.u.mem_write(0x20009000,b"\xcc"*0xf000)
        self.u.mem_write(0x200057d0,struct.pack("<I",0x2000))
        self.flash_events=[];self.power_loss=None
        self.reports=[];self.calls=[];self.waits=[];self.trace=[];self.busy=False;self.min_sp=RAM+0x7000
        self.u.hook_add(UC_HOOK_CODE,self.on_code)
        self.call(SYMBOLS["qmk_init_entry"])
        assert self.calls==["stock-late-init"]
        assert self.u.mem_read(0x20009000,0x7000)==b"\xcc"*0x7000
        end=SYMBOLS["__bss_end"]
        assert self.u.mem_read(end,0x20018000-end)==b"\xcc"*(0x20018000-end)
        assert self.owns()==1,"Boot must default to QMK after successful hardware typing tests"
    def on_code(self,u,address,size,data):
        self.min_sp=min(self.min_sp,u.reg_read(UC_ARM_REG_SP))
        if address in (0x47ac,0x2ed0,0x2fb0,0x12c0,0x1640,0x185c):
            raise AssertionError(f"Save called a removed original Flash function: {address:#x}")
        elif address==0x40e8:
            self.calls.append("stock-late-init")
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        elif address==0x10904:
            assert u.reg_read(UC_ARM_REG_R0)==0
            assert u.reg_read(UC_ARM_REG_R2)==8
            report=bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),8))
            if not self.busy:self.reports.append(report)
            u.reg_write(UC_ARM_REG_R0,2 if self.busy else 0)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        elif address==(SYMBOLS["wait_ms"]&~1):
            delay=u.reg_read(UC_ARM_REG_R0)
            assert delay==0,f"Unexpected blocking delay {delay} ms in basic typing path"
            assert delay<=200,f"Unexpected QMK wait duration: {delay}"
            self.waits.append({"ms":delay,"caller":hex(u.reg_read(UC_ARM_REG_LR))})
    def fmc_read(self,u,offset,size,data):
        assert size==4 and offset>=0x1000
        if offset==0x1048 and self.fmc_stuck_busy:return 1
        return self.fmc_regs.get(offset,0)
    def fmc_write(self,u,offset,size,value,data):
        if offset<512:
            self.fmc_fifo[offset:offset+size]=value.to_bytes(size,"little")
            return
        assert size==4 and offset in (0x1000,0x1004,0x1040,0x1050,0x1058),hex(offset)
        if offset==0x1050:self.fmc_regs[offset]=self.fmc_regs.get(offset,0)&~value;return
        self.fmc_regs[offset]=value
        if offset!=0x1040 or not value&1:return
        logical=self.fmc_regs[0x1004]*512-0x2000
        assert logical in NV_PAGES,f"FMC operation escaped settings pages: {logical:#x}"
        command=self.fmc_regs[0x1000]&0xfff
        if command==self.fmc_fail_on:
            self.fmc_regs[0x1040]=0;self.fmc_regs[0x1050]=2;self.fmc_regs[0x100c]=5
            return
        if command==1:
            u.mem_write(logical,b"\xff"*512);self.flash_events.append(("erase",logical))
            if self.power_loss=="after_erase":self.power_loss_triggered=True;u.emu_stop()
        elif command==2:
            payload=bytes(self.fmc_fifo)
            assert all((a&b)==b for a,b in zip(u.mem_read(logical,512),payload))
            if self.power_loss=="partial_program":
                u.mem_write(logical,payload[:64]);self.power_loss_triggered=True;u.emu_stop()
            else:u.mem_write(logical,payload);self.flash_events.append(("program",logical))
        else:raise AssertionError(f"Unexpected FMC command {command:#x}")
        self.fmc_regs[0x1040]=0;self.fmc_regs[0x1050]=1
    def periph_value(self,address):
        if address==0x4001f020:return (1<<24) if self.remap else 0
        if 0x4001f000<=address<0x40020000:return 0 # IHRC 12 MHz, no prescaler
        return (address^0x5a5a1234)&0xffffffff
    def periph_read(self,u,offset,size,data):
        assert size==4
        return self.periph_value(0x40000000+offset)
    def periph_write(self,u,offset,size,value,data):
        raise AssertionError(f"Unexpected peripheral write: {0x40000000+offset:#x}")
    def core_read(self,u,offset,size,data):
        assert size==4
        if offset==0x1004:
            self.dwt_cycles=(self.dwt_cycles+self.dwt_step)&0xffffffff
            return self.dwt_cycles
        return self.core_regs.get(offset,0)
    def core_write(self,u,offset,size,value,data):
        assert size==4 and offset in (0x1000,0xedfc),hex(offset)
        self.core_regs[offset]=value
    def call(self,address):
        u=self.u
        saved=[0x12345600+i for i in range(8)]
        regs=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
        for reg,v in zip(regs,saved):u.reg_write(reg,v)
        u.reg_write(UC_ARM_REG_SP,RAM+0x7000);u.reg_write(UC_ARM_REG_LR,STOP|1)
        u.emu_start(address|1,STOP,count=150000)
        if self.power_loss_triggered:raise SimulatedPowerLoss()
        assert u.reg_read(UC_ARM_REG_PC)==STOP,hex(u.reg_read(UC_ARM_REG_PC))
        assert u.reg_read(UC_ARM_REG_SP)==RAM+0x7000
        assert [u.reg_read(r) for r in regs]==saved,"Callee-saved registers corrupted"
        assert u.reg_read(UC_ARM_REG_PRIMASK)==0,"IRQ state not restored"
        return u.reg_read(UC_ARM_REG_R0)
    def owns(self):return self.call(SYMBOLS["qmk_keyboard_owned"])
    def step(self):
        now=struct.unpack("<I",self.u.mem_read(0x20000580,4))[0]+1
        self.u.mem_write(0x20000580,struct.pack("<I",now))
        self.call(SYMBOLS["qmk_bridge_task"])
    def press(self,name,value=150):
        self.u.mem_write(0x200040d8+NAMES[name]["electrical"]*2,struct.pack("<H",value));self.step()
    def release(self,name):self.press(name,0)
    def command(self,cmd,count=0,row=0,col=0,value=0,payload=None):
        packet=bytearray(64);packet[:5]=bytes((0xaa,cmd,count,row,col));packet[5:8]=b"B68"
        struct.pack_into("<H",packet,8,value)
        if payload:packet[8:8+len(payload)]=payload
        self.u.mem_write(RX,bytes(packet));self.u.mem_write(0x20000365,b"\x01")
        self.call(0xeb60)
        return bytes(self.u.mem_read(TX,64))
    def mode(self,on):
        r=self.command(0x78,int(on));assert r[2]==1 and r[8]==int(on)
        self.step();assert self.owns()==int(on)

tests=[]
m=Machine()
m.mode(False);m.reports.clear()
m.press("A")
assert not m.reports,"Shadow mode must not emit QMK keyboard reports"
r=m.command(0x74);assert r[8:12]==b"B68Q" and r[40+2]==4 and r[19]==0
assert m.command(0x78,1)[2]==255,"Must reject output-mode changes with a key held"
m.release("A");m.mode(True)
tests.append("QMK default boot, optional stock/shadow mode, and guarded output switch")

for key in MAPPING:
    if key["name"]=="Fn":continue
    e=key["electrical"]
    m.u.mem_write(0x200040d8+e*2,struct.pack("<H",150));m.step()
    usage=int(key["hid_usage"],0)
    report=m.reports[-1]
    if 0xe0<=usage<=0xe7:assert report[0]&(1<<(usage-0xe0)),key
    else:assert usage in report[2:],(key,report.hex())
    m.u.mem_write(0x200040d8+e*2,b"\0\0");m.step()
    assert m.reports[-1]==bytes(8),(key,"release stuck")
tests.append("All 66 non-Fn physical keys press/release through upstream QMK")

m.press("Fn");m.press("1")
assert m.reports[-1][2]==0x3a,m.reports[-1].hex()
m.release("Fn");m.release("1")
assert m.reports[-1]==bytes(8)
tests.append("Fn+1 -> F1 and releasing Fn before the other key")

for name in ("Fn","2"):
    m.u.mem_write(0x200040d8+NAMES[name]["electrical"]*2,struct.pack("<H",150))
m.step();assert m.reports[-1][2]==0x3b
m.release("Fn");m.release("2")
tests.append("Simultaneous Fn+2 honors the Fn layer before regular keys")

m.press("Fn");m.press("Q");assert 0x14 in m.reports[-1][2:]
m.release("Q");m.release("Fn")
m.press("W",99);assert m.reports[-1]==bytes(8)
m.press("W",100);assert 0x1a in m.reports[-1][2:]
m.press("W",80);assert 0x1a in m.reports[-1][2:]
m.press("W",79);assert m.reports[-1]==bytes(8)
tests.append("Transparent layer keys and 100/80 Hall-travel hysteresis")

a=NAMES["A"];r,c=divmod(a["raw_slot"],16)
assert m.command(0x75,0,r,c,5)[8:10]==b"\x05\0"
assert m.command(0x76,0,r,c)[8:10]==b"\x05\0"
m.press("A");assert 5 in m.reports[-1][2:]
assert m.command(0x75,0,r,c,4)[2]==255
m.release("A");assert m.reports[-1]==bytes(8)
assert m.command(0x75,0,r,c,4)[2]==2
for layer,row,col in [(2,0,0),(0,6,0),(0,0,16)]:assert m.command(0x75,layer,row,col,4)[2]==255
tests.append("Live RAM remap, readback, held-key rejection, and range checks")

m.busy=True;m.press("D");old=len(m.reports);m.step();assert len(m.reports)==old
m.busy=False;m.step();assert 7 in m.reports[-1][2:]
m.release("D");m.mode(False)
assert m.owns()==0
before=len(m.reports);m.call(0x13350);assert len(m.reports)>=before
tests.append("USB busy retry and fallback to original stock-report sender")

nv=Machine()
assert nv.command(0x79)[2]==255 and not nv.flash_events
nv.command(0x75,0,r,c,5)
nv.press("A")
assert nv.command(0x79,payload=b"SAVE")[2]==255 and not nv.flash_events
nv.release("A")
saved=nv.command(0x79,payload=b"SAVE")
assert saved[8:10]==b"\x01\x00" and struct.unpack_from("<I",saved,12)[0]==1
assert nv.flash_events==[("erase",NV_PAGES[0]),("program",NV_PAGES[0])]
assert nv.command(0x79,payload=b"SAVE")[8]==0 and len(nv.flash_events)==2
image_one=bytes(nv.u.mem_read(0,len(IMAGE)))
assert image_one[:NV_PAGES[0]]==IMAGE[:NV_PAGES[0]]
assert image_one[NV_PAGES[0]+512:]==IMAGE[NV_PAGES[0]+512:]
loaded=Machine(image_one)
assert loaded.command(0x76,0,r,c)[8:10]==b"\x05\0"
loaded.press("A");assert 5 in loaded.reports[-1][2:];loaded.release("A")
loaded.command(0x75,0,r,c,6)
saved=loaded.command(0x79,payload=b"SAVE")
assert saved[9]==1 and struct.unpack_from("<I",saved,12)[0]==2
image_two=bytes(loaded.u.mem_read(0,len(IMAGE)))
assert Machine(image_two).command(0x76,0,r,c)[8:10]==b"\x06\0"
tests.append("Unmodified SONiX SDK Flash HAL, inactive-page save, no-op save, and reboot reload")

guard=Machine()
for bad in (0,0x2000,0x7cfff,0x7d001,0x7d400,0x7dffc,0x7e000,0x400000):
    guard.u.reg_write(UC_ARM_REG_R0,bad);guard.u.reg_write(UC_ARM_REG_R1,RAM+0x6000)
    assert guard.call(SYMBOLS["sn34_flash_write_settings_page"])==0xffffffff
assert not guard.flash_events
guard.remap=False
assert guard.command(0x79,payload=b"SAVE")[2]==255 and not guard.flash_events
tests.append("Board wrapper rejects non-settings addresses and Boot-mode mapping before erase/program")

stuck=Machine();stuck.fmc_stuck_busy=True;stuck.dwt_step=12000000
assert stuck.command(0x79,payload=b"SAVE")[2]==255 and not stuck.flash_events
failed=Machine(image_one);failed.command(0x75,0,r,c,6);failed.fmc_fail_on=2
assert failed.command(0x79,payload=b"SAVE")[2]==255
assert Machine(bytes(failed.u.mem_read(0,len(IMAGE)))).command(0x76,0,r,c)[8:10]==b"\x05\0"
tests.append("Independent HAL timeout with interrupts masked, and failed program preserves the prior keymap")

bad=bytearray(image_two);bad[NV_PAGES[1]+32]^=1
assert Machine(bytes(bad)).command(0x76,0,r,c)[8:10]==b"\x05\0"
for failure in ("after_erase","partial_program"):
    interrupted=Machine(image_one);interrupted.command(0x75,0,r,c,6);interrupted.power_loss=failure
    try:interrupted.command(0x79,payload=b"SAVE")
    except SimulatedPowerLoss:pass
    else:raise AssertionError("Power-loss model was not triggered")
    restored=Machine(bytes(interrupted.u.mem_read(0,len(IMAGE))))
    assert restored.command(0x76,0,r,c)[8:10]==b"\x05\0"
wrap=bytearray(image_two)
for page,sequence in zip(NV_PAGES,(0xffffffff,0)):
    struct.pack_into("<I",wrap,page+8,sequence)
    struct.pack_into("<I",wrap,page+400,zlib.crc32(wrap[page:page+400]))
assert Machine(bytes(wrap)).command(0x76,0,r,c)[8:10]==b"\x06\0"
tests.append("CRC fallback, power loss during erase/program, and sequence rollover")

reset=Machine()
assert reset.command(0x7a)[2]==255
assert reset.command(0x7a,payload=b"REBT")[2]==1
assert reset.u.mem_read(SYMBOLS["reboot_pending"],1)==b"\x01"
tests.append("Explicit reboot signature and delayed reboot request")

for cmd in (0x70,0x71,0x72,0x73):
    if cmd==0x70:assert m.command(cmd)[8:12]==b"B68P"
    elif cmd==0x71:assert m.command(cmd,24)[2]==48
    elif cmd==0x73:assert m.command(cmd,48)[2]==48
tests.append("Original probe identity, ADC snapshots, and User-ROM reads remain reachable")

snapshot_status=m.command(0x74)
assert snapshot_status[12] in (3,4) and struct.unpack_from("<H",snapshot_status,58)[0]==len(REGISTERS)
for at in range(0,len(REGISTERS),12):
    count=min(12,len(REGISTERS)-at)
    response=m.command(0x7b,count,at&255,at>>8)
    assert response[2]==count*4 and struct.unpack_from("<H",response,3)[0]==at
    for i,item in enumerate(REGISTERS[at:at+count]):
        address=item["address"]
        if address>=0x40000000:expected=m.periph_value(address)
        elif address>=RAM:expected=struct.unpack("<I",m.u.mem_read(address,4))[0]
        else:expected=m.fmc_regs.get(address-0x00600000,0)
        assert struct.unpack_from("<I",response,8+i*4)[0]==expected,item
for count,at in ((0,0),(13,0),(1,len(REGISTERS)),(2,len(REGISTERS)-1)):
    assert m.command(0x7b,count,at&255,at>>8)[2]==255
tests.append("Fixed read-only hardware snapshot list, cross-packet offsets and bounds")

trial=Machine()
assert trial.command(0x7c)[2]==255
native=MANIFEST.get("native_usb_trial")
if native:
    blob=(ROOT/"build/native_usb/native_usb.bin").read_bytes()
    assert IMAGE[0x30000:0x30000+len(blob)]==blob and hashlib.sha256(blob).hexdigest()==native["image_sha256"]
    assert trial.command(0x7c,payload=b"NUSB")[2]==1
    assert trial.u.mem_read(SYMBOLS["reboot_pending"],1)==b"\x02"
else:assert trial.command(0x7c,payload=b"NUSB")[2]==255
tests.append("Native USB trial is hash-pinned, requires its explicit signature and is deferred until after ACK")

pe=pefile.PE(str(BUILD/"BAT68_QMK_BRIDGE_v118.exe"))
resources={item.id:item.directory.entries[0].data.struct for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries if ty.id==10 for item in ty.directory.entries}
assert pe.get_data(resources[4000].OffsetToData,resources[4000].Size)==IMAGE
check=sum(struct.unpack(f"<{len(IMAGE)//2}H",IMAGE))&0xffff
assert pe.get_data(resources[4014].OffsetToData,8).decode("utf-16le")==f"{check:04X}"
assert pe.verify_checksum()
tests.append("OEM package embeds exact tested QMK bridge and matching checksums")

result={"status":"PASS_OFFLINE_NOT_FLASHED","tests":tests,"image_sha256":hashlib.sha256(IMAGE).hexdigest(),
        "updater_sha256":hashlib.sha256((BUILD/"BAT68_QMK_BRIDGE_v118.exe").read_bytes()).hexdigest(),
        "maximum_observed_stack_bytes":0x20007000-m.min_sp,
        "nonzero_wait_calls":[w for w in m.waits if w["ms"]],
        "memory_protection":"ROM is read/execute; only RAM is writable; FMC MMIO is modeled and restricted to settings pages",
        "emulator_note":"UC_HOOK_MEM_WRITE distorts IT blocks in the isolated check_thumb_emulator.py reproduction; memory protection enforces write boundaries instead",
        "limits":["USB transmission was stubbed; FMC registers and flash hardware effects were modeled", "ADC travel values were supplied by the test", "Real typing, nonvolatile save and restart still require hardware validation"]}
(BUILD/"test_results.json").write_text(json.dumps(result,indent=2))
MANIFEST["status"]="PASS_OFFLINE_NOT_FLASHED"
(BUILD/"manifest.json").write_text(json.dumps(MANIFEST,indent=2))
print(json.dumps(result,indent=2))
