# /// script
# dependencies = ["unicorn"]
# ///
"""Expand the stock scatter-loaded RAM in an emulator, without running main."""
from pathlib import Path
import json
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC

root=Path(__file__).resolve().parents[1]
data=(root/"analysis/binary_2_rcdata_4000_0.bin").read_bytes()
uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
uc.mem_map(0,0x80000);uc.mem_write(0,data)
uc.mem_map(0x20000000,0x28000)
uc.reg_write(UC_ARM_REG_SP,struct.unpack_from("<I",data)[0])
def stop_at_main(u,address,size,unused):
    if address==0x12844:u.emu_stop()
uc.hook_add(UC_HOOK_CODE,stop_at_main)
uc.emu_start(0x1c1,0,count=300000)
assert uc.reg_read(UC_ARM_REG_PC)==0x12844,"Initialization did not reach main"
ram=bytes(uc.mem_read(0x20000000,0x28000))
(root/"analysis/stock_initialized_ram.bin").write_bytes(ram)
descriptors=[]
for i in range(len(ram)-18):
    if ram[i:i+2]==b"\x12\x01":
        v=struct.unpack_from("<BBHBBBBHHHBBBB",ram,i)
        if v[6] in (8,16,32,64) and v[13] in (1,2):
            descriptors.append({"ram_address":hex(0x20000000+i),"vid":hex(v[7]),"pid":hex(v[8]),"bcdDevice":hex(v[9]),"bytes":ram[i:i+18].hex()})
result={"reached_main":True,"usb_descriptors":descriptors}
(root/"analysis/stock_usb_identity.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
