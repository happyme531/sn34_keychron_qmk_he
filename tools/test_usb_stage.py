# /// script
# dependencies = ["unicorn", "hidapi"]
# ///
"""Run exact stock ARM dispatcher + read/modify/write helper for all stage frames.

Flash erase/program primitives and busy status are hardware models. The stock
dispatcher, address arithmetic, 512-byte merge, and Flash API wrappers execute
as real ARM instructions. This performs no USB I/O or real Flash operation.
"""
import json
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from stage_probe_usb import inputs,write_frame,PAGE,PAGE_SIZE,BUILD,digest

STOCK,TARGET,FRAMES,PLAN=inputs()
RAM=0x20000000
STOP=0x100000
uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
uc.mem_map(0,0x80000);uc.mem_write(0,STOCK)
uc.mem_map(RAM,0x28000);uc.mem_map(STOP,0x1000)
# This is set by stock init after testing SCU REMAP=1. Hardware controller page
# zero is the Boot region, and the stock API adds its 8 KiB user-ROM offset.
uc.mem_write(0x200057d0,struct.pack("<I",0x2000))
flash_events=[]
ram_writes=[]

def return_zero(u):
    u.reg_write(UC_ARM_REG_R0,0)
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))

def on_code(u,address,size,data):
    if address==0x185c:  # Hardware busy-status poll: report completed.
        return_zero(u)
    elif address==0x12c0:  # Physical-page erase primitive.
        physical=u.reg_read(UC_ARM_REG_R0)*512
        logical=physical-0x2000
        assert logical==PAGE, f"Erase would escape unused page: {physical:#x}"
        flash_events.append({"operation":"erase","physical_offset":hex(physical),"logical":hex(logical)})
        u.mem_write(logical,b"\xff"*512)
        return_zero(u)
    elif address==0x1640:  # Program one 512-byte page from stock scratch buffer.
        physical=u.reg_read(UC_ARM_REG_R0)
        logical=physical-0x2000
        assert logical==PAGE, f"Program would escape unused page: {physical:#x}"
        source=u.reg_read(UC_ARM_REG_R1)
        assert source==0x200031cd, f"Unexpected stock page buffer: {source:#x}"
        payload=bytes(u.mem_read(source,512))
        before=bytes(u.mem_read(logical,512))
        assert all((a&b)==b for a,b in zip(before,payload))
        u.mem_write(logical,payload)
        flash_events.append({"operation":"program","logical":hex(logical),"bytes":512})
        return_zero(u)

def on_write(u,access,address,size,value,data):
    ram_writes.append((address,size))
    assert RAM<=address and address+size<=RAM+0x28000, f"Unexpected CPU write: {address:#x}"

uc.hook_add(UC_HOOK_CODE,on_code)
uc.hook_add(UC_HOOK_MEM_WRITE,on_write)
expected=bytearray(STOCK)
for index,packet in enumerate(FRAMES):
    uc.mem_write(0x20003668,packet)
    uc.mem_write(0x20000365,b"\x01")
    uc.mem_write(0x20000364,b"\x00")
    uc.reg_write(UC_ARM_REG_SP,RAM+0x27000)
    uc.reg_write(UC_ARM_REG_LR,STOP|1)
    uc.emu_start(0xeb61,STOP,count=100000)
    assert uc.reg_read(UC_ARM_REG_PC)==STOP,hex(uc.reg_read(UC_ARM_REG_PC))
    assert uc.reg_read(UC_ARM_REG_SP)==RAM+0x27000
    assert bytes(uc.mem_read(0x20000365,1))==b"\0"
    assert bytes(uc.mem_read(0x20000364,1))==b"\x01"
    at=PAGE+index*48
    expected[at:at+packet[2]]=packet[8:8+packet[2]]
    # Compare ALL user ROM after each exact stock write, not just the destination.
    assert bytes(uc.mem_read(0,len(STOCK)))==expected
assert bytes(uc.mem_read(PAGE,512))==TARGET
assert bytes(uc.mem_read(0xeb60,4))==bytes.fromhex("2de9f84f")
assert len(flash_events)==2*len(FRAMES)

rejected=0
for address,data in [(0xea00,b"1234"),(PAGE-1,b"1"),(PAGE,b""),(PAGE,b"x"*49),
                     (PAGE+511,b"12"),(PAGE+512,b"x"),(0,b"x"),(0x00200000,b"x")]:
    try:write_frame(address,data)
    except ValueError:rejected+=1
    else:raise AssertionError("Out-of-scope write was accepted")

result={"status":"PASS_OFFLINE_ONLY", "stage_packets":len(FRAMES),
        "stock_512_byte_erases":len(FRAMES),"stock_512_byte_programs":len(FRAMES),
        "only_logical_page_touched":hex(PAGE),"only_physical_offset_touched":hex(PAGE+0x2000),
        "entire_user_rom_compared_after_each_packet":True,"hook_unchanged":True,
        "rejected_out_of_scope_writes":rejected,"staged_page_sha256":digest(TARGET),
        "limitation":"Flash primitives/busy status are emulated; hardware programming is untested"}
(BUILD/"usb_stage_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
