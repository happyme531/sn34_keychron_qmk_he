# /// script
# dependencies = ["capstone"]
# ///
"""Compare a partial live ROM read with the offline OEM image."""
from pathlib import Path
import json
import re
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

root = Path(__file__).resolve().parents[1]
live = (root/"analysis/live_v118_window_clean_a.bin").read_bytes()
old = (root/"analysis/binary_2_rcdata_4000_0.bin").read_bytes()
base=0x9200
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail=True

for pattern in (bytes.fromhex("aa55a55aff0033cc"),bytes.fromhex("aa42895aff7162cc"),
                bytes.fromhex("01032000"),b"[USBD]",b"SN34",b"KEYBOARD",b"EWEADN",b"SONiX"):
    print("PATTERN",pattern.hex(),[hex(base+m.start()) for m in re.finditer(re.escape(pattern),live)])

for start,length in [(0xe448,32),(0x13130,32),(0xd7e8,8)]:
    p=old[start:start+length]
    hits=[base+m.start() for m in re.finditer(re.escape(p),live)]
    print("EXACT",hex(start),length,[hex(a) for a in hits],p.hex())

records=[]
if (root/"analysis/live_v118_magic.bin").exists():
    part=(root/"analysis/live_v118_magic.bin").read_bytes()
    at=0xf488-base
    print("MAGIC BULK",live[at:at+len(part)].hex())
    print("MAGIC DIRECT",part.hex())
    print("MAGIC DIFFERENCES",[(i,hex(a),hex(b)) for i,(a,b) in enumerate(zip(live[at:],part)) if a!=b])
for at in range(0,len(live)-4,4):
    v=struct.unpack_from("<I",live,at)[0]
    if v in (0x5aa555aa,0xcc3300ff,0x5a8942aa,0xcc6271ff,0x200301):
        records.append({"constant":hex(v),"address":hex(base+at)})
        for insn in md.disasm(live[max(0,at-100):at],base+max(0,at-100)):
            print(f"{insn.address:08x} {insn.mnemonic} {insn.op_str}")
print(json.dumps(records,indent=2))
(root/"analysis/live_window_constants.json").write_text(json.dumps(records,indent=2))
