# /// script
# dependencies = ["pefile", "unicorn", "pyelftools", "capstone"]
# ///
"""Preserve compatible BAT68 settings when installing a tested Launcher build.

Only the two configuration banks are copied. The new executable code, unused
Flash and retained Boot policy come from the separately verified base package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import zlib
import re
import pefile
from storage import LAYOUT, HEADER, read_banks, normalize_via_tag
from build_config import BuildPaths

ROOT = Path(__file__).resolve().parents[2]
SIZE = LAYOUT.eeprom_size
V22_CODE_SHA = "13b9d76819b2165580951f4010998f77c1f355ed66d2272b9e578ef7e166ba12"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--generation",help="Optional output label, for example v37; not a storage-format selector")
    parser.add_argument("--brightness",type=int,choices=range(256))
    parser.add_argument("--build-dir",type=Path,default=BuildPaths.environment().build)
    parser.add_argument("--package-dir",type=Path,help="Verified base package; defaults to <build-dir>_ota")
    parser.add_argument("--output-dir",type=Path)
    args = parser.parse_args()
    if args.generation and not re.fullmatch(r"[A-Za-z0-9_-]+",args.generation):
        parser.error("generation must be a simple output label")
    build=(ROOT/args.build_dir).resolve()
    os.environ["SN34_NATIVE_BUILD"]=str(build)
    from test_bat68 import Keyboard, IMAGE, SYMS
    previous = args.backup.read_bytes()
    assert len(previous) == LAYOUT.app_size
    v22 = sha(previous[:63040]) == V22_CODE_SHA
    # Layout identity/CRC and actual new-firmware startup are the acceptance
    # criteria. Only v22 needs a code identity for its former RGB enumeration.
    base = (ROOT/args.package_dir).resolve() if args.package_dir else build.with_name(build.name+"_ota")
    suffix="_"+args.generation+"_update" if args.generation else "_update"
    default_output=build.with_name(build.name+suffix)
    output = (ROOT/args.output_dir).resolve() if args.output_dir else default_output
    verified = json.loads((base / "test_results.json").read_text())
    manifest = json.loads((base / "manifest.json").read_text())
    app = bytearray((base / "application.bin").read_bytes())
    wrapper = bytearray((base / "SN34_QMK_HE_v2.exe").read_bytes())
    assert verified["status"] == "PASS_OFFLINE_NOT_FLASHED"
    assert sha(app) == manifest["image_sha256"] == verified["image_sha256"]
    assert sha(wrapper) == verified["updater_sha256"]
    assert app[:len(IMAGE)] == IMAGE and sha(IMAGE) == manifest["source_code_sha256"]
    effects = json.loads((build / "rgb_effects.json").read_text())
    names = ("SOLID_COLOR", "SOLID_COLOR", "BREATHING", "CYCLE_LEFT_RIGHT", "SOLID_REACTIVE_SIMPLE")
    records = []
    for saved in read_banks(previous):
        bank,sequence,header=saved["bank"],saved["sequence"],saved["header"]
        data=bytearray(saved["payload"])
        old_via_magic=normalize_via_tag(data)
        # eeprom_core_t is packed; RGB's first byte is at offset 23 and packs
        # a two-bit enable field followed by a six-bit effect enum.
        rgb=LAYOUT.rgb_core_offset
        old_mode = data[rgb] >> 2
        if v22:
            assert old_mode < len(names), "Unexpected v22 effect ID"
            new_mode = effects.index(names[old_mode]) + 1
        else:
            assert 1 <= old_mode <= len(effects), "Unexpected v23 effect ID"
            new_mode = old_mode
        data[rgb] = (new_mode << 2) | (data[rgb] & 3)
        if args.brightness is not None:
            data[rgb] |= 1
            data[LAYOUT.rgb_value_offset] = args.brightness
        new_header = bytearray(header)
        struct.pack_into("<I", new_header, 16, zlib.crc32(data))
        struct.pack_into("<I", new_header, HEADER.size-4, zlib.crc32(new_header[:HEADER.size-4]))
        app[bank:bank + SIZE] = data
        app[bank + SIZE:bank + LAYOUT.eeprom_bank_size] = new_header
        records.append(dict(bank=hex(bank), sequence=sequence, old_rgb_mode=old_mode,
                            new_rgb_mode=new_mode, payload_sha256=sha(data),
                            old_via_magic=old_via_magic.hex(),new_via_magic=LAYOUT.via_magic.hex()))
    assert records, "No valid settings bank in backup"
    assert app[:LAYOUT.code_limit] == (base / "application.bin").read_bytes()[:LAYOUT.code_limit]
    assert app[LAYOUT.eeprom_end:] == (base / "application.bin").read_bytes()[LAYOUT.eeprom_end:]
    # Execute actual startup with the migrated banks. Compare all 7,680 bytes,
    # which covers keymaps, macros, calibration, HE profiles and RGB settings.
    machine = Keyboard(bytes(app[LAYOUT.code_limit:]))
    sequence = machine.call("sn34_eeprom_sequence")
    selected = next(r for r in records if r["sequence"] == sequence)
    bank = int(selected["bank"], 16)
    assert bytes(machine.u.mem_read(SYMS["cache"], SIZE)) == app[bank:bank + SIZE], "Preserved bank changed during startup: incompatible layout or invalid settings"
    assert machine.call("rgb_matrix_get_mode") == selected["new_rgb_mode"]
    if args.brightness is not None:
        assert machine.call("rgb_matrix_get_val") == args.brightness
    pe = pefile.PE(data=bytes(wrapper))
    resources = {item.id:item.directory.entries[0].data.struct
                 for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries if ty.id == 10
                 for item in ty.directory.entries}
    assert resources[4000].Size == len(app)
    offset = pe.get_offset_from_rva(resources[4000].OffsetToData)
    wrapper[offset:offset + len(app)] = app
    checksum = sum(struct.unpack(f"<{len(app)//2}H", app)) & 0xffff
    offset = pe.get_offset_from_rva(resources[4014].OffsetToData)
    wrapper[offset:offset + 8] = f"{checksum:04X}".encode("utf-16le")
    pe = pefile.PE(data=bytes(wrapper))
    struct.pack_into("<I", wrapper, pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), pe.generate_checksum())
    pe = pefile.PE(data=bytes(wrapper))
    assert pe.verify_checksum() and pe.get_data(resources[4000].OffsetToData, len(app)) == app
    output.mkdir(exist_ok=True)
    (output / "application.bin").write_bytes(app)
    (output / "SN34_QMK_HE_v2.exe").write_bytes(wrapper)
    manifest.update(image_sha256=sha(app), checksum=f"0x{checksum:04X}",
                    settings_source=str(args.backup), settings_source_sha256=sha(previous),
                    preserved_settings_banks=records, base_package=str(base))
    verified.update(image_sha256=sha(app), updater_sha256=sha(wrapper),
                    settings_migration="Normalized the VIA compatibility tag and restored the complete EEPROM cache through actual new firmware startup",
                    preserved_sequence=sequence, settings_banks=records)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "test_results.json").write_text(json.dumps(verified, indent=2), encoding="utf-8")
    print(json.dumps(dict(output=str(output), sequence=sequence, banks=records,
                          image_sha256=sha(app), checksum=manifest["checksum"]), indent=2))


if __name__ == "__main__":
    main()
