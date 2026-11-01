# /// script
# dependencies = ["unicorn", "capstone", "pefile"]
# ///
"""Execute the real ARM patch in Unicorn; compare fallback against stock."""
from pathlib import Path
import argparse
import hashlib
import json
import random
import struct

import pefile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from probe_profiles import PROFILES

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--stock",choices=PROFILES,default="118")
args=parser.parse_args()
PROFILE=PROFILES[args.stock]
BUILD=ROOT/"build"/f"v{args.stock}"
STOCK = (ROOT / PROFILE["base"]).read_bytes()
PATCH = (BUILD / f"bat68_probe_stock_v{args.stock}.bin").read_bytes()
RAM, RAM_SIZE = 0x20000000, 0x28000
RX, TX, READY, PENDING = [PROFILE[k] for k in ("rx","tx","ready","pending")]
STOP = 0x00100000
REGS = [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,
        UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,
        UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]

def request(cmd, count=0, offset=0, tag=b"B68"):
    b=bytearray(64)
    b[0:3]=bytes([0xaa,cmd,count])
    if cmd==0x73:
        struct.pack_into("<I",b,8,offset)
    else:
        struct.pack_into("<H",b,3,offset)
    b[5:8]=tag
    return bytes(b)

def execute(image, packet, pending=1, initial=None):
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0,0x80000); uc.mem_write(0,image)
    uc.mem_map(RAM,RAM_SIZE)
    if initial is not None: uc.mem_write(RAM,initial)
    uc.mem_map(STOP,0x1000)
    uc.mem_map(0x00200000,0x2000)
    boot=bytes((i*17+3)&255 for i in range(8192))
    uc.mem_write(0x00200000,boot)
    uc.mem_write(RX,packet); uc.mem_write(PENDING,bytes([pending])); uc.mem_write(READY,b"\0")
    raw=[1000+i*7 for i in range(96)]
    uc.mem_write(PROFILE["raw"],struct.pack("<96H",*raw))
    initial_regs=[0x12340000+i*0x101 for i in range(13)]
    for r,v in zip(REGS,initial_regs): uc.reg_write(r,v)
    uc.reg_write(UC_ARM_REG_SP,RAM+RAM_SIZE-0x100)
    uc.reg_write(UC_ARM_REG_LR,STOP|1)
    writes=[]
    def on_write(u,access,address,size,value,data): writes.append((address,size))
    uc.hook_add(UC_HOOK_MEM_WRITE,on_write)
    uc.emu_start(PROFILE["hook"]|1,STOP,count=20000)
    assert uc.reg_read(UC_ARM_REG_PC)==STOP,hex(uc.reg_read(UC_ARM_REG_PC))
    assert uc.reg_read(UC_ARM_REG_SP)==RAM+RAM_SIZE-0x100
    assert [uc.reg_read(r) for r in REGS[4:12]]==initial_regs[4:12],"Callee-saved register corrupted"
    assert uc.reg_read(UC_ARM_REG_PRIMASK)==0,"Interrupt state not restored"
    assert all(RAM<=a and a+s<=RAM+RAM_SIZE for a,s in writes),"Write outside RAM"
    return bytes(uc.mem_read(TX,64)),bytes(uc.mem_read(RAM,RAM_SIZE)),writes

def main():
    tests=[]
    def passed(name): tests.append(name)
    # Verify the trampoline returns to the original literal-load successor.
    ins=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(PATCH[0x18000:0x18020],0x18000))
    assert any(i.mnemonic=="b.w" and i.op_str==f"#0x{PROFILE['resume']:x}" for i in ins)
    passed("trampoline relocation target")
    tx,_,_=execute(PATCH,request(0x70))
    assert tx[:3]==bytes([0x55,0x70,24]) and tx[8:12]==b"B68P" and tx[12]==2
    assert tx[20:28]==bytes.fromhex(PROFILE["base_sha"])[:8]
    assert struct.unpack_from("<H",tx,16)[0]==int(args.stock,16)
    passed("probe identity")
    # Every possible legal raw window, including single samples and all endpoints.
    for count in range(1,25):
        for offset in range(97-count):
            tx,_,_=execute(PATCH,request(0x71,count,offset))
            assert tx[2]==2*count
            assert struct.unpack_from(f"<{count}H",tx,8)==tuple(1000+i*7 for i in range(offset,offset+count))
    passed("all 2028 valid raw sample windows")
    for count,offset in [(0,0),(25,0),(1,96),(24,73),(1,65535),(255,0)]:
        tx,_,_=execute(PATCH,request(0x71,count,offset)); assert tx[2]==255
    passed("raw range rejection")
    for offset,count in [(0,48),(0x300,32),(8191,1),(8144,48)]:
        tx,_,_=execute(PATCH,request(0x72,count,offset)); assert tx[2]==count
        assert tx[8:8+count]==bytes((i*17+3)&255 for i in range(offset,offset+count))
    for offset,count in [(8192,1),(8191,2),(0,49),(0,0),(65535,1)]:
        tx,_,_=execute(PATCH,request(0x72,count,offset)); assert tx[2]==255
    passed("Boot-region bounds and byte reads")
    for offset,count in [(0,48),(4,8),(0x8400,48),(0x7dff0,16),(0x7dfff,1)]:
        tx,_,_=execute(PATCH,request(0x73,count,offset))
        assert tx[2]==count and tx[8:8+count]==PATCH[offset:offset+count]
        assert struct.unpack_from("<I",tx,56)[0]==offset
    for offset,count in [(0,0),(0,49),(0x7e000,1),(0x7dfff,2),(0xffffffff,1),(0x20000000,1)]:
        tx,_,_=execute(PATCH,request(0x73,count,offset));assert tx[2]==255
    passed("User-ROM reads, zero address, full-width offsets, and bounds")
    rng=random.Random(68)
    packets=[request(0x13),request(0x70,tag=b"BAD"),request(0x71,1,0,tag=b"BAD"),request(0x66),request(0x67)]
    packets += [request(rng.choice([0x30,0x31,0x40,0x50,0x60,0x68,0x69,0x70]),tag=b"BAD") for _ in range(15)]
    for n,p in enumerate(packets):
        # Same SRAM, excluding ephemeral stack frames, must match the stock path.
        a,ra,_=execute(STOCK,p)
        b,rb,_=execute(PATCH,p)
        assert a==b,(n,p.hex(),a.hex(),b.hex())
        assert ra[:0x27000]==rb[:0x27000],(n,"fallback modified persistent RAM state")
    for p in [request(0x70),request(0x71,24)]:
        a,ra,_=execute(STOCK,p,pending=0)
        b,rb,_=execute(PATCH,p,pending=0)
        assert a==b and ra[:0x27000]==rb[:0x27000]
    passed("22 original-handler fallback scenarios")
    # Verify the generated OEM wrapper carries the exact tested image and checksum.
    pe=pefile.PE(str(BUILD/f"BAT68_EXPERIMENTAL_PROBE_stock_v{args.stock}.exe"))
    blobs={}
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if typ.id==10:
            for e in typ.directory.entries:
                leaf=e.directory.entries[0].data.struct
                blobs[e.id]=pe.get_data(leaf.OffsetToData,leaf.Size)
    assert blobs[4000]==PATCH
    checksum=sum(struct.unpack(f"<{len(PATCH)//2}H",PATCH))&65535
    assert blobs[4014].decode("utf-16le")==f"{checksum:04X}"
    assert pe.verify_checksum()
    passed("OEM updater image, MCU checksum, and PE checksum")
    result={"status":"PASS_OFFLINE_ONLY","tests":tests,"image_sha256":hashlib.sha256(PATCH).hexdigest(),
            "stock_version":args.stock,
            "limitations":["No real USB timing test", "Boot-region reads may be protected on actual hardware", "No real Flash erase/program test"]}
    (BUILD/"probe_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
