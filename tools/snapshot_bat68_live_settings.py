# /// script
# dependencies = ["hidapi", "unicorn", "pyelftools", "capstone"]
# ///
"""Export public live settings without writing the connected keyboard.

Reconstruct a migration bank using the tested firmware EEPROM routines. This
is for the old firmware's over-strict release guard: committed core preferences
remain the base, while all readable settings are overlaid from the live device.
The original Flash readback is retained separately and never overwritten.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import zlib

os.environ["BAT68_NATIVE_BUILD"] = "build/bat68"
from bat68 import Raw
from bat68_probe import Probe
from bat68_qmk import status
from test_bat68 import Keyboard, SYMS, SCRATCH

ROOT = Path(__file__).resolve().parents[1]
SIZE = 7680
BANKS = (0x79000, 0x7b000)


def sha(data): return hashlib.sha256(data).hexdigest()


def capture(raw):
    def buffer(command, size):
        result = bytearray()
        for offset in range(0, size, 26 if command == 0xa9 else 28):
            count = min(26 if command == 0xa9 else 28, size-offset)
            if command == 0xa9:
                request = bytes((0xa9, 0x12, profile, offset & 255, offset >> 8, count))
                reply = raw.query(request); assert reply[:6] == request
                result += reply[6:6+count]
            else:
                request = bytes((command, offset >> 8, offset & 255, count))
                reply = raw.query(request); assert reply[:4] == request
                result += reply[4:4+count]
        return result.hex()
    info = raw.he(0x10)
    profile_size = int.from_bytes(info[4:6], "little")
    assert info[3] == 3 and profile_size == 860
    macro_size = int.from_bytes(raw.query((13,))[1:3], "big")
    assert macro_size == 3992 and raw.query((12,))[1] == 16
    calibration = bytearray()
    for row in range(6):
        for col in range(16):
            reply = raw.he(0x42, bytes((row, col)))
            assert reply[2:5] == bytes((row, col, 0))
            zero, bottom = struct.unpack_from("<2H", reply, 5)
            assert zero < 4096 and bottom < 4096
            calibration += (zero | bottom << 12).to_bytes(3, "little")
    profiles = []
    for profile in range(3): profiles.append(buffer(0xa9, profile_size))
    phase = raw.he(0x41)
    assert phase[3] == 0, "Finish manual calibration before snapshotting"
    rgb = {}
    for field, count in ((1,1), (2,1), (3,1), (4,2)):
        rgb[str(field)] = list(raw.query((8,3,field))[3:3+count])
    return dict(profile=info[2], profiles=profiles, calibration_flags=phase[2],
        calibration=calibration.hex(), curve=raw.he(0x20)[2:10].hex(),
        controller=raw.he(0x22)[3], keymaps=buffer(18,768), macros=buffer(14,macro_size),
        rgb=rgb, default_layer=raw.query((0xa3,))[1], nkro=raw.query((0xa7,0x12))[3]&1,
        layout=raw.query((2,2))[2:6].hex())


def main():
    destination = ROOT / "backups" / datetime.now().strftime("live_settings_%Y%m%d_%H%M%S")
    destination.mkdir()
    probe = Probe(); raw = Raw()
    try:
        before = status(probe)
        assert before["protocol"] == 8 and not any(before["matrix"])
        app = probe.app_dump(); boot = probe.boot_dump()
        assert sha(app[:74816]) == "720c96686e1ec7b5d5b772f9aad6f439a05bd6b2d76bbab8b1e98e672ca1141d"
        assert sha(boot) == "b6006ef843ef5dd4e285c9e06dc04f717326b620ce08a6dfe2b17decbd310d0e"
        (destination / "original_flash_app.bin").write_bytes(app)
        (destination / "original_boot.bin").write_bytes(boot)
        live = capture(raw)
        assert capture(raw) == live, "Live configuration changed during the snapshot; retry"
        after = status(probe)
        assert after["saved_sequence"] == before["saved_sequence"] and not any(after["matrix"])
    finally:
        raw.close(); probe.close()
    machine = Keyboard(app[0x79000:])
    original_cache = bytes(machine.u.mem_read(SYMS["cache"], SIZE))
    def update(offset, data):
        machine.u.mem_write(SCRATCH, data)
        machine.call("eeprom_update_block", SCRATCH, offset, len(data))
    # Pinned Keychron layout: 37-byte core, flags/profile, 96 packed 12+12-bit
    # calibration pairs, three 860-byte profiles, curve, gamepad mode, VIA.
    update(37, bytes((live["calibration_flags"], live["profile"])))
    update(39, bytes.fromhex(live["calibration"]))
    update(327, b"".join(bytes.fromhex(p) for p in live["profiles"]))
    update(2907, bytes.fromhex(live["curve"]) + bytes((live["controller"],)))
    for function, field in (("dynamic_keymap_set_buffer", "keymaps"),
                            ("dynamic_keymap_macro_set_buffer", "macros")):
        data = bytes.fromhex(live[field]); machine.u.mem_write(SCRATCH, data)
        machine.call(function, 0, len(data), SCRATCH)
    machine.raw_command(bytes((3,2)) + bytes.fromhex(live["layout"]))
    for field, values in live["rgb"].items(): machine.raw_command(bytes((7,3,int(field))) + bytes(values))
    machine.raw_command(bytes((9,3)))
    if machine.raw_command(bytes((0xa3,)))[1] != live["default_layer"]:
        machine.call("set_single_persistent_default_layer", live["default_layer"])
    if machine.raw_command(bytes((0xa7,0x12)))[3]&1 != live["nkro"]:
        assert machine.raw_command(bytes((0xa7,0x13,live["nkro"])))[2] == 0
    cache = bytes(machine.u.mem_read(SYMS["cache"], SIZE))
    records = []
    for bank in BANKS:
        h = struct.unpack_from("<7I", app, bank+SIZE)
        if h[:2] == (0x45483842,1) and h[3] == SIZE and h[5] == 0x4845434d and h[4] == zlib.crc32(app[bank:bank+SIZE]) and h[6] == zlib.crc32(app[bank+SIZE:bank+SIZE+24]):
            records.append((h[2],bank))
    sequence, current = max(records)
    target = BANKS[1] if current == BANKS[0] else BANKS[0]
    header = bytearray(512)
    struct.pack_into("<6I", header,0,0x45483842,1,sequence+1,SIZE,zlib.crc32(cache),0x4845434d)
    struct.pack_into("<I", header,24,zlib.crc32(header[:24]))
    prepared = bytearray(app);prepared[target:target+SIZE]=cache;prepared[target+SIZE:target+8192]=header
    loaded = Keyboard(bytes(prepared[0x79000:]))
    assert bytes(loaded.u.mem_read(SYMS["cache"],SIZE)) == cache
    assert capture(type("EmulatedRaw", (), {"query":lambda self,data:loaded.raw_command(bytes(data)),
        "he":lambda self,cmd,payload=b"":loaded.raw_command(bytes((0xa9,cmd))+bytes(payload))})()) == live
    (destination / "prepared_migration_app.bin").write_bytes(prepared)
    (destination / "live_settings.json").write_text(json.dumps(live,indent=2),encoding="utf-8")
    report = dict(status="PUBLIC_LIVE_SETTINGS_CAPTURED_AND_STARTUP_VERIFIED",device_writes=False,
        original_application_sha256=sha(app),prepared_application_sha256=sha(prepared),
        source_sequence=sequence,prepared_sequence=sequence+1,changed_cache_bytes=sum(a!=b for a,b in zip(cache,original_cache)),
        directory=str(destination.relative_to(ROOT)),prepared_file=str((destination/"prepared_migration_app.bin").relative_to(ROOT)),
        limits=["Core preferences without a public read command retain their latest committed bytes; default layer, NKRO and RGB are captured live.",
                "Prepared migration file contains reconstructed settings; original Flash readback is stored separately."])
    (destination / "manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    (ROOT / "analysis/pre_v28_live_settings.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__": main()
