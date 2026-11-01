"""Shared evidence manifest for Clang and the standard QMK Make build."""
from pathlib import Path
import hashlib
import json
import os
from functools import lru_cache
from elftools.elf.elffile import ELFFile
from build_config import ROOT, BuildPaths, resolve_input, board_directory, keyboard_name
from storage import LAYOUT
from model import load_board

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
    target=json.loads((board_directory()/"target.json").read_text(encoding="utf-8"))
    code=(build/"firmware.bin").read_bytes();assert 0<len(code)<LAYOUT.code_limit
    with (build/"firmware.elf").open("rb") as stream:
        elf=ELFFile(stream);symbols={s.name:s.entry.st_value for s in elf.get_section_by_name(".symtab").iter_symbols()}
    assert symbols["__data_start"]==LAYOUT.ram_origin and symbols["__bss_end"]<=LAYOUT.bss_limit
    assert int.from_bytes(code[:4],"little")==LAYOUT.stack_top
    app=bytearray(LAYOUT.app_size);app[:len(code)]=code
    app[LAYOUT.footer_address:LAYOUT.footer_address+4]=LAYOUT.footer_magic.to_bytes(4,"little")
    (build/"application.bin").write_bytes(app)
    record=lambda paths:[dict(path=locations.label(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(set(paths))]
    manifest=dict(status="BUILT_NOT_TESTED_NOT_FLASHED",qmk_platform=True,keychron_he=True,**config,
        build_backend="QMK CLI/Make",compiler_description=compiler,
        bytes=len(code),image_sha256=hashlib.sha256(code).hexdigest(),application_sha256=hashlib.sha256(app).hexdigest(),
        rom_start="0x0",ram_start=hex(symbols["__data_start"]),ram_end=hex(symbols["__bss_end"]),entry=hex(symbols["sn34_reset_entry"]),
        standalone=True,cold_initialization_included=True,qmk_keyboard_included=True,bringup_guard_enabled=False,
        original_application_inputs=[],original_application_calls=[],he_eeprom_banks=list(map(hex,LAYOUT.eeprom_banks)),he_eeprom_bytes=LAYOUT.eeprom_size,
        storage_format=LAYOUT.eeprom_version,via_eeprom_date=LAYOUT.via_eeprom_date,matrix_abi=load_board()["matrix"],
        hardware_verified=False,features=target['features'],test_only=target.get('test_only',False),
        bootloader_backend=target['bootloader'],travel_units="0..240 normalized stroke; physical millimetres not calibrated",
        calibration_model=(board_directory()/"hall_curve.json").relative_to(ROOT).as_posix(),
        sources=record(sources),build_inputs=record(inputs),keychron_patches=patches,
        limits=["New production image has not been flashed; cold boot, physical USB, OTA and power cycles require hardware validation",
                "Hall bottoms are initial estimates; normalized travel is not a measured displacement in millimetres",
                "Board-specific analog behavior, lighting and USB-host behavior require hardware validation",
                "The vendor SDK is supplied externally and is not included in this source tree"])
    (build/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("sources","build_inputs","keychron_patches")},indent=2))


def common_inputs(build,locations=None):
    locations=locations or BuildPaths.environment()
    qmk=locations.qmk
    folders=[ROOT/'util/sn34', ROOT/'platforms/sn34', ROOT/'tmk_core/protocol/sn34',
             ROOT/'drivers/analog', ROOT/'tests/sn34', board_directory().parent,
             qmk/'keyboards/keychron/common/analog_matrix']
    suffixes={'.py','.sh','.ps1','.c','.h','.S','.inc','.mk','.ld','.json','.patch','.toml','.lock'}
    items=set()
    for folder in folders:
        for directory,children,files in os.walk(folder):
            children[:]=[name for name in children if name not in ('.venv','__pycache__')]
            for name in files:
                path=Path(directory)/name
                if path.suffix in suffixes and path.is_file():items.add(path)
    items.update(ROOT/p for p in ('drivers/eeprom/sn34_banked.c','drivers/eeprom/sn34_storage.c',
        'drivers/eeprom/sn34_eeprom.h','drivers/eeprom/sn34.mk','drivers/led/ws2812_sn34.c','drivers/led/sn34_rgb_effects.h'))
    items.update(build/name for name in ('build_config.json','patches.json','sn34_via.json','sn34_launcher.json','rgb_effects.json','rgb_protocol.json','sn34_memory.generated.ld'))
    items.update(build.rglob('*.h'))
    items.update((qmk/'keyboards/keychron/common/nkro.c',qmk/'keyboards/keychron/common/keychron_raw_hid.c',qmk/'quantum/via.c',qmk/'tmk_core/protocol/usb_descriptor.c',locations.sdk/'Middlewares/Source/USB_Device/Class/HID/usbd_hid.c'))
    return items
