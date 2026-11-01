# /// script
# dependencies = ["unicorn"]
# ///
from pathlib import Path
import struct
from unicorn import *
from unicorn.arm_const import *
image=(Path(__file__).resolve().parents[1]/"build/qmk_bridge/bat68_qmk_bridge_v118.bin").read_bytes()
for hook in (False,True):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
    u.mem_map(0,0x80000);u.mem_write(0,image)
    u.mem_map(0x20000000,0x28000);u.mem_map(0x100000,0x1000)
    u.mem_write(0x20010000,struct.pack("<I",0x20010100))
    u.mem_write(0x20010100,b"\0\0\x04\0\0\0\0\0")
    u.reg_write(UC_ARM_REG_R0,4);u.reg_write(UC_ARM_REG_LR,0x100001);u.reg_write(UC_ARM_REG_SP,0x20007000)
    seen=[]
    if hook:u.hook_add(UC_HOOK_CODE,lambda uc,a,s,d:seen.append(hex(a)))
    if hook:u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,s,v,d:None)
    u.emu_start(0x18a51,0x100000,count=100)
    print("hook",hook,"pc",hex(u.reg_read(UC_ARM_REG_PC)),"r2",u.reg_read(UC_ARM_REG_R2),"trace",seen)
