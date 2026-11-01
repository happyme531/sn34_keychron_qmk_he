# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Run the real source-built USB stack; model only PCD hardware transfers."""
import hashlib
import json
import os
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UcError,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/os.environ.get("BAT68_NATIVE_BUILD","build/native_usb")
MANIFEST=json.loads((BUILD/"manifest.json").read_text())
IMAGE=(BUILD/"native_usb.bin").read_bytes()
with (BUILD/"native_usb.elf").open("rb") as stream:
    elf=ELFFile(stream)
    SYMS={s.name:s.entry.st_value for s in elf.get_section_by_name(".symtab").iter_symbols()}
BASE=int(MANIFEST["rom_start"],0)
def source_code_address(address):
    return BASE<=address<BASE+len(IMAGE)
STOP=0x100000
SCRATCH=0x20026000 if MANIFEST.get("keychron_he") else 0x20020000

class Machine:
    def __init__(self):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        self.u.mem_map(BASE,0x20000,UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(BASE,IMAGE)
        self.u.mem_map(0x20000000,0x28000,UC_PROT_READ|UC_PROT_WRITE)
        self.u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        # Native init's one explicit detach bit; PCD handles all other hardware.
        self.u.mem_map(0x40000000,0x100000,UC_PROT_READ|UC_PROT_WRITE)
        data=bytes(self.u.mem_read(SYMS["__data_load"],SYMS["__data_end"]-SYMS["__data_start"]))
        self.u.mem_write(SYMS["__data_start"],data)
        self.transfers=[];self.receives=[];self.endpoints=[];self.stalls=[];self.trace=[]
        self.stub_names=("HAL_Delay","HAL_PCD_Init","HAL_PCD_Start","HAL_PCD_ForceFullSpeed",
                         "HAL_PCD_EP_Transmit","HAL_PCD_EP_Receive","HAL_PCD_EP_Open",
                         "HAL_PCD_EP_Close","HAL_PCD_EP_SetStall","HAL_PCD_EP_ClrStall",
                         "HAL_PCD_SetAddress","HAL_PCD_EP_GetRxCount")
        self.stub_addresses={SYMS[name]&~1:name for name in self.stub_names if name in SYMS}
        self.u.hook_add(UC_HOOK_CODE,self.on_code)
    def on_code(self,u,address,size,data):
        assert source_code_address(address),f"Execution left native source-built ROM: {address:#x}"
        self.trace.append(address)
        if len(self.trace)>16:self.trace.pop(0)
        name=self.stub_addresses.get(address)
        if not name:return
        args=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if name=="HAL_PCD_EP_Transmit":
            self.transfers.append((args[1],bytes(u.mem_read(args[2],args[3])) if args[3] else b""))
        elif name=="HAL_PCD_EP_Receive":self.receives.append(tuple(args[1:]))
        elif name=="HAL_PCD_EP_Open":self.endpoints.append(tuple(args[1:]))
        elif name=="HAL_PCD_EP_SetStall":self.stalls.append(args[1])
        u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def call(self,name,*args):
        u=self.u
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,0x20027f00);u.reg_write(UC_ARM_REG_LR,STOP|1)
        try:u.emu_start(SYMS[name]|1,STOP,count=5000000 if MANIFEST.get("qmk_platform") else 2000000 if MANIFEST.get("keychron_he") else 200000)
        except UcError as exc:
            regs={f"r{i}":hex(u.reg_read(reg)) for i,reg in enumerate((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4))}
            raise RuntimeError({"call":name,"pc":hex(u.reg_read(UC_ARM_REG_PC)),"registers":regs,"trace":[hex(v) for v in self.trace]}) from exc
        assert u.reg_read(UC_ARM_REG_PC)==STOP,(name,hex(u.reg_read(UC_ARM_REG_PC)))
        assert u.reg_read(UC_ARM_REG_SP)==0x20027f00
        assert u.reg_read(UC_ARM_REG_PRIMASK)==0
        return u.reg_read(UC_ARM_REG_R0)
    def setup(self,bm,request,value=0,index=0,length=0):
        self.u.mem_write(SCRATCH,struct.pack("<BBHHH",bm,request,value,index,length))
        return self.call("USBD_SetupStage",SYMS["device"],SCRATCH)

def main():
    tests=[]
    vectors=struct.unpack_from("<112I",IMAGE)
    assert vectors[0]==0x20028000 and vectors[1]==SYMS["native_trial_entry"]
    assert vectors[16+77]==SYMS["USB_HS_IRQHandler"]
    if "ADC0_IRQHandler" in SYMS:assert vectors[16+18]==SYMS["ADC0_IRQHandler"]
    assert all(source_code_address(v&~1) for v in vectors[1:])
    tests.append("Complete native interrupt table references only source-built code")
    machine=Machine()
    assert machine.call("native_usb_init")==0
    tests.append("Real SDK core/HID initialization with four interfaces")
    assert machine.setup(0x80,6,0x0100,0,18)==0
    descriptor=machine.transfers[-1][1]
    assert len(descriptor)==18 and descriptor[0:2]==b"\x12\x01"
    assert struct.unpack_from("<HH",descriptor,8)==(0x0c45,0x8037)
    tests.append("GET_DESCRIPTOR device identity and EP0 control transfer")
    assert machine.setup(0x80,6,0x0200,0,255)==0
    configuration=machine.transfers[-1][1]
    assert configuration[:2]==b"\x09\x02" and configuration[4]==4
    assert struct.unpack_from("<H",configuration,2)[0]==len(configuration)
    at=0;interfaces=[];endpoints=[]
    while at<len(configuration):
        length,kind=configuration[at:at+2]
        assert length>=2 and at+length<=len(configuration)
        if kind==4:interfaces.append(configuration[at+2])
        if kind==5:endpoints.append(configuration[at+2])
        at+=length
    assert interfaces==[0,1,2,3] and endpoints==[0x81,0x82,0x83,3,4],endpoints
    tests.append("Four HID interfaces, valid total descriptor size and endpoint assignment")
    # Interface report descriptors are served after enumeration (addressed state).
    machine.call("USBD_Reset",SYMS["device"])
    assert machine.setup(0,5,7)==0
    for interface,length in ((0,63),(1,23),(2,34),(3,35)):
        assert machine.setup(0x81,6,0x2200,interface,512)==0
        report=machine.transfers[-1][1]
        assert len(report)==length,(interface,len(report))
        assert report[-1]==0xc0
        if interface==2:assert report[:3]==bytes.fromhex("0668ff") and bytes.fromhex("95408102") in report
        if interface==3:assert report[:3]==bytes.fromhex("0667ff") and bytes.fromhex("9600109102") in report and bytes.fromhex("9540b102") in report
    tests.append("GET_DESCRIPTOR report routing for keyboard, consumer, diagnostics and ISP HID")
    assert machine.setup(0,9,1)==0
    assert not machine.stalls,machine.stalls
    tests.append("SET_ADDRESS and SET_CONFIGURATION reach configured state without stalls")
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),
            "tests":tests,"hardware_stubs":list(machine.stub_addresses.values()),
            "limits":["PCD register access, PHY behavior, DMA, clock and watchdog timing still require hardware tests",
                      "ADC, QMK keyboard and clock validation are recorded separately when included"]}
    (BUILD/"test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    manifest=json.loads((BUILD/"manifest.json").read_text())
    manifest["status"]=result["status"]
    (BUILD/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
