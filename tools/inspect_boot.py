# /// script
# dependencies = ["capstone"]
# ///
"""Inspect the twice-read, physical Boot region; no hardware access."""
from pathlib import Path
import hashlib
import json
import re
import struct
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB

root=Path(__file__).resolve().parents[1]
data=(root/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
base=0x00200000
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
result={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
        "distinct_bytes":len(set(data)),"zero_bytes":data.count(0),"ff_bytes":data.count(255),
        "first_32_words":[hex(v) for v in struct.unpack_from("<32I",data)],
        "strings":[{"address":hex(base+m.start()),"text":m.group().decode()} for m in re.finditer(rb"[ -~]{5,}",data)],
        "app_upgrade_entry":hex(base+0x300)}
for pattern in (bytes.fromhex("450c1072"),bytes.fromhex("aa55a55aff0033cc"),b"\x12\x01",b"\x09\x02"):
    result["pattern_"+pattern.hex()]=[hex(base+m.start()) for m in re.finditer(re.escape(pattern),data)]
code="\n".join(f"{i.address:08x}  {i.mnemonic} {i.op_str}" for i in md.disasm(data[0x300:0x3c0],base+0x300))
(root/"analysis/boot_entry.asm").write_text(code)
(root/"analysis/boot_summary.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2));print(code)
