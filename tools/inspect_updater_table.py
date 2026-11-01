# /// script
# dependencies = ["pefile", "capstone"]
# ///
"""Read chip profiles and selected code from the OEM updater; never execute it."""
from pathlib import Path
import json
import struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

root = Path(__file__).resolve().parents[1]
pe = pefile.PE(str(root / "analysis/oem_updater_v110.exe"))
base = pe.OPTIONAL_HEADER.ImageBase
def read(va, length):
    return pe.get_data(va-base, length)

profiles = []
for i in range(22):
    va = 0x5a9ad0 + i*0x33
    b = read(va, 0x33)
    profiles.append({"index":i, "address":hex(va), "bytes":b.hex(),
                     "boot_vid":hex(struct.unpack_from("<H",b,4)[0]),
                     "boot_pid":hex(struct.unpack_from("<H",b,6)[0]),
                     "feature_payload_bytes":struct.unpack_from("<I",b,0x17)[0]})
text = json.dumps(profiles, indent=2)
(root / "analysis/updater_chip_profiles.json").write_text(text)
print(text)
md = Cs(CS_ARCH_X86, CS_MODE_32)
for va, length in [(0x40b520,0x80), (0x40d4c0,0x1d0)]:
    print(f"\nCODE {va:08x}")
    for insn in md.disasm(read(va,length),va):
        print(f"{insn.address:08x}  {insn.mnemonic} {insn.op_str}")
