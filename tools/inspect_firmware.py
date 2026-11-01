"""Offline image comparison and Thumb literal-reference inspection."""
from pathlib import Path
import hashlib
import json
import re
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from intelhex import IntelHex

root = Path(__file__).resolve().parents[1]
out = root / "analysis"
primary = (out / "binary_2_rcdata_4000_0.bin").read_bytes()
hexfile = out / "settings/Settings/FWFiles/SN34F280_User.hex"
ih = IntelHex(str(hexfile))
secondary = bytes(ih.tobinarray(start=0, end=len(primary)-1, pad=0))
(out / "skin_hex_image.bin").write_bytes(secondary)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = True
images = []
for name, data in [("primary_rcdata4000", primary), ("secondary_skin_hex", secondary)]:
    words = struct.unpack_from("<48I", data)
    matches = []
    for label, value in [("isp_magic_1", 0x5aa555aa), ("isp_magic_2", 0xcc3300ff), ("boot_base", 0x7e000), ("image_end", 0x7dffc), ("reset_aircr", 0xe000ed0c)]:
        matches.extend({"label": label, "value": hex(value), "offset": hex(m.start())} for m in re.finditer(re.escape(struct.pack("<I",value)), data))
    info = {"name": name, "length": len(data), "sha256": hashlib.sha256(data).hexdigest(), "initial_sp":hex(words[0]), "reset":hex(words[1]), "vectors":[hex(x) for x in words], "patterns":matches}
    images.append(info)
    # Decode at every halfword to avoid a preceding data table desynchronizing code.
    refs = []
    for off in range(0,min(len(data),0x20000)-4,2):
        ins = next(md.disasm(data[off:off+4],off,count=1),None)
        if ins and ins.mnemonic.startswith("ldr") and "[pc," in ins.op_str:
            nums = re.findall(r"#(0x[0-9a-f]+|[0-9]+)",ins.op_str)
            if nums:
                target = ((off+4)&~3)+int(nums[0],0)
                if target+4<=len(data):
                    val=struct.unpack_from("<I",data,target)[0]
                    if val in (0x5aa555aa,0xcc3300ff,0x7e000,0x7dffc,0xe000ed0c):
                        refs.append(f"0x{off:08x}: {ins.mnemonic} {ins.op_str} -> [0x{target:x}]=0x{val:08x}")
    (out / f"{name}_boot_refs.txt").write_text("\n".join(refs),encoding="utf-8")
(out / "firmware_summary.json").write_text(json.dumps({"identical":primary==secondary,"images":images},indent=2),encoding="utf-8")
print(json.dumps({"identical":primary==secondary,"images":images},indent=2))
