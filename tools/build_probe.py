# /// script
# dependencies = ["pefile", "capstone"]
# ///
"""Build a pinned stock+probe image and an OEM-updater copy. Does NOT flash."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import subprocess

import pefile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from probe_profiles import PROFILES

ROOT = Path(__file__).resolve().parents[1]
EXT = 0x18000

def thumb_branch(source, target):
    delta = target - (source + 4)
    assert delta % 2 == 0 and -(1 << 24) <= delta < (1 << 24)
    imm = delta & 0x1FFFFFF
    s, i1, i2 = (imm >> 24) & 1, (imm >> 23) & 1, (imm >> 22) & 1
    j1, j2 = 1 ^ i1 ^ s, 1 ^ i2 ^ s
    return struct.pack("<HH", 0xF000 | (s << 10) | ((imm >> 12) & 0x3FF),
                       0x9000 | (j1 << 13) | (j2 << 11) | ((imm >> 1) & 0x7FF))

def checksum(data):
    return sum(struct.unpack(f"<{len(data)//2}H", data)) & 0xFFFF

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock",choices=PROFILES,default="118")
    args=parser.parse_args()
    profile=PROFILES[args.stock]
    BUILD=ROOT/"build"/f"v{args.stock}"
    BASE=ROOT/profile["base"]
    BASE_SHA,EXE_SHA=profile["base_sha"],profile["wrapper_sha"]
    HOOK=profile["hook"]
    BUILD.mkdir(exist_ok=True,parents=True)
    llvm = Path(os.environ.get("BAT68_LLVM", r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\ARM64\bin"))
    clang = llvm / "clang.exe"
    objcopy = llvm / "llvm-objcopy.exe"
    src = ROOT / "firmware/probe"
    elf = BUILD / "bat68_probe.elf"
    run = [str(clang), "--target=arm-none-eabi", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft",
           "-ffreestanding", "-fno-builtin", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
           "-fno-stack-protector", "-fno-pic", "-Os", "-Wall", "-Wextra", "-Werror", "-nostdlib",
           "-fno-delete-null-pointer-checks",
           f"-DBAT68_VERSION={args.stock}", "-fuse-ld=lld", f"-Wl,-T,{src/'probe.ld'}", f"-Wl,-Map,{BUILD/'bat68_probe.map'}",
           f"-Wl,--defsym,stock_dispatch_resume={profile['resume']}",
           str(src / "hook.S"), str(src / "probe.c"), "-o", str(elf)]
    subprocess.run(run, check=True)
    subprocess.run([str(objcopy), "-O", "binary", str(elf), str(BUILD / "probe_extension.bin")], check=True)
    original = BASE.read_bytes()
    assert hashlib.sha256(original).hexdigest() == BASE_SHA, "Wrong stock base"
    assert original[HOOK:HOOK+4] == bytes.fromhex(profile["prefix"]), "Hook prefix changed"
    if args.stock=="110":
        assert struct.unpack_from("<I", original, 0xDBD4)[0] == profile["pending"], "Relocated literal changed"
    ext = (BUILD / "probe_extension.bin").read_bytes()
    assert len(ext) < 4096 and not any(original[EXT:EXT+4096]), "Extension area not empty"
    result = bytearray(original)
    branch = thumb_branch(HOOK, EXT)
    decoded = next(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(branch, HOOK))
    assert decoded.mnemonic == "b.w" and decoded.op_str == f"#0x{EXT:x}", decoded
    result[HOOK:HOOK+4] = branch
    result[EXT:EXT+len(ext)] = ext
    assert result[:0x1C0] == original[:0x1C0], "Vector table changed"
    assert result[0x1D8:0x23C] == original[0x1D8:0x23C], "Reset/ISP entry changed"
    assert result[0x8000:0xB800] == original[0x8000:0xB800], "Stock config changed"
    assert result[0x7DFFC:] == original[0x7DFFC:] == bytes.fromhex("5555aaaa"), "Boot marker changed"
    binary = BUILD / f"bat68_probe_stock_v{args.stock}.bin"
    binary.write_bytes(result)
    oem=ROOT/profile["wrapper"]
    assert hashlib.sha256(oem.read_bytes()).hexdigest()==EXE_SHA, "Wrong OEM updater"
    exe = bytearray(oem.read_bytes())
    pe = pefile.PE(data=bytes(exe))
    locations = {}
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if typ.id == 10:
            for resource in typ.directory.entries:
                leaf = resource.directory.entries[0].data.struct
                locations[resource.id] = (pe.get_offset_from_rva(leaf.OffsetToData), leaf.Size)
    offset, size = locations[4000]
    assert size == len(result) and exe[offset:offset+size] == original
    exe[offset:offset+size] = result
    check_offset, check_size = locations[4014]
    expected = f"{checksum(original):04X}".encode("utf-16le")
    assert check_size == 8 and exe[check_offset:check_offset+8] == expected
    exe[check_offset:check_offset+8] = f"{checksum(result):04X}".encode("utf-16le")
    # PE checksum has no relation to the MCU checksum, but keep the wrapper consistent.
    pe = pefile.PE(data=bytes(exe))
    struct.pack_into("<I", exe, pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), pe.generate_checksum())
    wrapper = BUILD / f"BAT68_EXPERIMENTAL_PROBE_stock_v{args.stock}.exe"
    wrapper.write_bytes(exe)
    manifest = {
        "status": "OFFLINE_TESTING_REQUIRED_NOT_FLASHED",
        "stock_sha256": BASE_SHA,
        "stock_halfword_checksum": f"0x{checksum(original):04X}",
        "stock_version": "1."+args.stock[1:],
        "image_sha256": hashlib.sha256(result).hexdigest(),
        "image_halfword_checksum": f"0x{checksum(result):04X}",
        "wrapper_sha256": hashlib.sha256(exe).hexdigest(),
        "hook": {"address": hex(HOOK), "original": original[HOOK:HOOK+4].hex(), "patched": branch.hex()},
        "extension": {"address": hex(EXT), "length": len(ext)},
        "boot_region": "0x00200000..0x00201FFF; contents and protection not yet read on device",
        "notes": ["Uses original OEM flashing code", "Embedded skin ZIP is unchanged; primary RCDATA 4000 is the selected image", "New commands 0x70..0x73 require B68 tag", "No flash operation in the diagnostic extension", "No hardware flashing is performed by this build script"]
    }
    (BUILD / "probe_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
