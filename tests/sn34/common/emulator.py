# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Run the real source-built USB stack; model only PCD hardware transfers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"util/sn34"))

import hashlib
import json
import os
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UcError,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *

from build_config import ROOT, BuildPaths
from storage import LAYOUT
BUILD=Path(os.environ["SN34_NATIVE_BUILD"]) if "SN34_NATIVE_BUILD" in os.environ else BuildPaths.environment().build
MANIFEST=json.loads((BUILD/"manifest.json").read_text())
IMAGE=(BUILD/"firmware.bin").read_bytes()
with (BUILD/"firmware.elf").open("rb") as stream:
    elf=ELFFile(stream)
    SYMS={s.name:s.entry.st_value for s in elf.get_section_by_name(".symtab").iter_symbols()}
BASE=int(MANIFEST["rom_start"],0)
def source_code_address(address):
    return BASE<=address<BASE+len(IMAGE)
STOP=0x100000
SCRATCH=LAYOUT.bss_limit+0x2000
STACK=LAYOUT.stack_top-192

class Machine:
    def __init__(self):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        self.u.mem_map(BASE,(len(IMAGE)+4095)&~4095,UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(BASE,IMAGE)
        self.u.mem_map(LAYOUT.ram_origin,LAYOUT.ram_size,UC_PROT_READ|UC_PROT_WRITE)
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
        u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,STOP|1)
        try:u.emu_start(SYMS[name]|1,STOP,count=5000000 if MANIFEST.get("qmk_platform") else 2000000 if MANIFEST.get("keychron_he") else 200000)
        except UcError as exc:
            regs={f"r{i}":hex(u.reg_read(reg)) for i,reg in enumerate((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4))}
            raise RuntimeError({"call":name,"pc":hex(u.reg_read(UC_ARM_REG_PC)),"registers":regs,"trace":[hex(v) for v in self.trace]}) from exc
        assert u.reg_read(UC_ARM_REG_PC)==STOP,(name,hex(u.reg_read(UC_ARM_REG_PC)))
        assert u.reg_read(UC_ARM_REG_SP)==STACK
        assert u.reg_read(UC_ARM_REG_PRIMASK)==0
        return u.reg_read(UC_ARM_REG_R0)
    def setup(self,bm,request,value=0,index=0,length=0):
        self.u.mem_write(SCRATCH,struct.pack("<BBHHH",bm,request,value,index,length))
        return self.call("USBD_SetupStage",SYMS["device"],SCRATCH)
