"""Shared evidence manifest for Clang and the standard QMK Make build."""
from pathlib import Path
import hashlib
import json
import os
from functools import lru_cache
from elftools.elf.elffile import ELFFile
from bat68_build_config import ROOT, BuildPaths, resolve_input
from bat68_storage import LAYOUT
from bat68_model import load_board

@lru_cache(maxsize=8192)
def dependency_item(cwd,token,roots):
    if os.name=="nt" and token.startswith("/mnt/") and len(token)>7:token=token[5].upper()+":/"+token[7:]
    item=(cwd/token).resolve()
    return item if item.is_file() and any(item.is_relative_to(root) for root in roots) else None


def dependencies(paths,cwd,locations=None):
    found=set()
    roots=tuple({ROOT,*([locations.build,*locations.roots().values()] if locations else [])})
    for path in paths:
        # -MMD inputs in this workspace have no spaces. Ignore -MP targets.
        for token in path.read_text().replace("\\\n"," ").split()[1:]:
            if token.endswith(":"):continue
            item=dependency_item(cwd,token,roots)
            if item is not None:found.add(item)
    return found


def write_manifest(build,sources,inputs,compiler,patches,locations=None):
    locations=locations or BuildPaths.environment()
    config=json.loads((build/"build_config.json").read_text(encoding="utf-8"))
    code=(build/"native_usb.bin").read_bytes();assert 0<len(code)<LAYOUT.code_limit
    with (build/"native_usb.elf").open("rb") as stream:
        elf=ELFFile(stream);symbols={s.name:s.entry.st_value for s in elf.get_section_by_name(".symtab").iter_symbols()}
    assert symbols["__data_start"]==LAYOUT.ram_origin and symbols["__bss_end"]<=LAYOUT.bss_limit
    assert int.from_bytes(code[:4],"little")==LAYOUT.stack_top
    app=bytearray(LAYOUT.app_size);app[:len(code)]=code
    app[LAYOUT.footer_address:LAYOUT.footer_address+4]=LAYOUT.footer_magic.to_bytes(4,"little")
    (build/"bat68_native_app.bin").write_bytes(app)
    record=lambda paths:[dict(path=locations.label(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(set(paths))]
    manifest=dict(status="BUILT_NOT_TESTED_NOT_FLASHED",qmk_platform=True,keychron_he=True,**config,
        build_backend="QMK CLI/Make",compiler_description=compiler,
        bytes=len(code),image_sha256=hashlib.sha256(code).hexdigest(),application_sha256=hashlib.sha256(app).hexdigest(),
        rom_start="0x0",ram_start=hex(symbols["__data_start"]),ram_end=hex(symbols["__bss_end"]),entry=hex(symbols["native_trial_entry"]),
        standalone=True,cold_initialization_included=True,qmk_keyboard_included=True,bringup_guard_enabled=False,
        original_application_inputs=[],original_application_calls=[],he_eeprom_banks=list(map(hex,LAYOUT.eeprom_banks)),he_eeprom_bytes=LAYOUT.eeprom_size,
        storage_format=LAYOUT.eeprom_version,via_eeprom_date=LAYOUT.via_eeprom_date,matrix_abi=load_board()["matrix"],
        hardware_verified=False,travel_units="0..240 normalized stroke with stock type-1 magnetic curve; physical millimetres not calibrated",
        calibration_model="firmware/board/hall_curve.json (derived numeric calibration data, no stock executable code)",
        sources=record(sources),build_inputs=record(inputs),keychron_patches=patches,
        limits=["New production image has not been flashed; cold boot, physical USB, OTA and power cycles require hardware validation",
                "Hall bottoms are initial estimates; normalized travel is not a measured displacement in millimetres",
                "RGB chain layout/pins and Windows XInput driver binding require hardware validation; RGB defaults on at brightness 32",
                "SDK redistribution permission remains unresolved; see analysis/sdk_license_review.json"])
    (build/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("sources","build_inputs","keychron_patches")},indent=2))


def common_inputs(build,locations=None):
    locations=locations or BuildPaths.environment()
    qmk=locations.qmk
    items={ROOT/"tools"/name for name in ("build_bat68.py","prepare_bat68.py","bat68_build_config.py",
        "bat68_board.py","bat68_patches.py","keychron_sources.py","bat68_artifacts.py","launcher_definition.py",
        "import_qmk_build.py","build_bat68_qmk.sh","bat68_model.py","bat68_storage.py")}
    items.update((ROOT/"firmware/qmk/bat68.ld",ROOT/"firmware/qmk/upstream.json",build/"build_config.json",build/"patches.json"))
    items.update(p for p in (ROOT/"patches").rglob("*") if p.is_file())
    items.update(build/name for name in ("bat68_via.json","bat68_launcher.json","rgb_effects.json","rgb_protocol.json"))
    items.update((ROOT/"firmware/board/hall_curve.json",ROOT/"firmware/board/bat68.json",ROOT/"firmware/board/storage.json",
        build/"bat68_memory.generated.ld"))
    items.add(ROOT/"tools/hall_curve.py")
    for folder in (qmk/"platforms/sn34",qmk/"keyboards/battle68",qmk/"tmk_core/protocol/sn34"):
        items.update(p for p in folder.rglob("*") if p.is_file())
    items.update(p for p in (qmk/"keyboards/keychron/common/analog_matrix").iterdir() if p.suffix in (".c",".h"))
    items.update((qmk/"keyboards/keychron/common/nkro.c",qmk/"keyboards/keychron/common/keychron_raw_hid.c",qmk/"quantum/via.c",qmk/"tmk_core/protocol/usb_descriptor.c",
        locations.sdk/"Middlewares/Source/USB_Device/Class/HID/usbd_hid.c"))
    items.add(ROOT/"firmware/board/keymap_overrides.json")
    items.update(build.rglob("*.h"))
    return items
