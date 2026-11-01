# /// script
# dependencies = ["pyelftools"]
# ///
"""Build native USB/ADC trials or the complete QMK application from source."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/"analysis/sdk/sn34f28x_sdk_2.1.4/SDK/HAL"
SRC=ROOT/"firmware/native"
BUILD=ROOT/"build/native_usb"

def main():
    global BUILD
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan",action="store_true",help="Include the source-built board ADC/mux driver")
    parser.add_argument("--keyboard",action="store_true",help="Include QMK keys, Hall travel and settings; implies --scan")
    parser.add_argument("--cold-init",action="store_true",help="Initialize clocks and board GPIO from source instead of inheriting them")
    parser.add_argument("--trial-ms",type=int,default=10000,help="Automatic return deadline, at most 300000 ms")
    parser.add_argument("--standalone",action="store_true",help="Build the complete reset-vector application at User ROM offset zero")
    parser.add_argument("--keychron-he",action="store_true",help="Build Keychron QMK with its complete analog matrix core; implies --standalone")
    parser.add_argument("--output",type=Path,help="Separate output directory within the workspace")
    parser.add_argument("--bringup-guard",action="store_true",help="Keep standalone footer invalid until explicit host commit")
    args=parser.parse_args()
    if args.keychron_he: args.standalone=True
    if args.standalone:
        args.keyboard=True;args.cold_init=True;BUILD=ROOT/"build/native_app"
    if args.keychron_he: BUILD=ROOT/"build/keychron_he"
    if args.output:
        BUILD=(ROOT/args.output).resolve()
        if not BUILD.is_relative_to(ROOT): parser.error("--output must stay within this workspace")
    if args.bringup_guard and not args.standalone:parser.error("--bringup-guard requires --standalone")
    if args.keyboard:args.scan=True
    if not 1000<=args.trial_ms<=300000:parser.error("Trial duration must be 1000..300000 ms")
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/"manifest.json").write_text(json.dumps({"status":"BUILDING_NOT_FLASHED"}),encoding="utf-8")
    llvm=Path(os.environ.get("BAT68_LLVM",r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\ARM64\bin"))
    includes=[SRC,ROOT/"firmware/board",SDK/"Com",SDK.parent.parent/"Board",SDK/"Peripherals/Include",SDK/"Peripherals/Source",
              SDK/"Middlewares/Include",SDK/"Middlewares/Source/USB_Device/Core",SDK/"Middlewares/Source/USB_Device/Class/HID",
              ROOT/"analysis/sdk/SONiX.SN34F2_DFP.2.0.4/Device/Include",ROOT/"reference/CMSIS_5/CMSIS/Core/Include",
              ROOT/"toolchains/newlib/extracted/usr/include/newlib"]
    flags=["--target=arm-none-eabi","-mcpu=cortex-m4","-mthumb","-mfloat-abi=soft","-std=gnu11",f"-DBAT68_ENABLE_SCAN={int(args.scan)}",
           f"-DBAT68_ENABLE_KEYBOARD={int(args.keyboard)}",f"-DBAT68_TRIAL_MILLISECONDS={args.trial_ms}u",
           f"-DBAT68_COLD_INIT={int(args.cold_init)}",
           f"-DBAT68_STANDALONE={int(args.standalone)}",
           f"-DBAT68_BRINGUP_GUARD={int(args.bringup_guard)}",
           f"-DBAT68_KEYCHRON_HE={int(args.keychron_he)}",
           "-ffreestanding","-fno-builtin","-fno-delete-null-pointer-checks","-fno-unwind-tables","-fno-asynchronous-unwind-tables",
           "-fno-stack-protector","-fno-pic","-fshort-enums","-ffunction-sections","-fdata-sections",
           "-Os","-Wall","-Wextra","-Wno-unused-parameter","-Wno-sign-compare","-Wno-type-limits"]
    sources=[SRC/n for n in ("startup.S","main.c","timebase.c","runtime.c","usb.c")]
    sources += [ROOT/"firmware/common/memory.c"]
    if args.cold_init:
        sources += [SRC/"clock.c",SDK/"Peripherals/Source/sn34f28x_hal_gpio.c",SDK/"Peripherals/Source/sn34f28x_hal_scu.c"]
        if not args.keyboard:sources += [SDK/"Peripherals/Source/sn34f28x_hal_flash.c",SDK/"Peripherals/Source/sn34f28x_hal_flash_ex.c"]
    if args.keyboard:
        qmk=ROOT/("keychron_qmk" if args.keychron_he else "qmk_firmware")
        sha=subprocess.check_output(["git","-C",str(qmk),"rev-parse","HEAD"],text=True).strip()
        assert sha==("2b493ff95f2665db719b1e95c91babb5036e72f3" if args.keychron_he else "180f394b489c238cb231c2bf8b080262155e03c0")
        includes += [BUILD,ROOT/"firmware/qmk_bridge",qmk/"quantum",qmk/"platforms",ROOT/"firmware/qmk_bridge/platform",qmk/"tmk_core/protocol",ROOT/"firmware/probe"]
        includes += sorted({p.parent for p in (qmk/"quantum").rglob("*.h")}-set(includes))
        flags += ["-include",str(ROOT/("firmware/keychron/config.h" if args.keychron_he else "firmware/qmk_bridge/config.h")),"-DBAT68_NATIVE_TIMEBASE=1"]
        mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
        overrides=json.loads((ROOT/"firmware/board/keymap_overrides.json").read_text())
        maps=[[["KC_NO"]*16 for _ in range(6)],[["KC_TRNS"]*16 for _ in range(6)]]
        for k in mapping:
            r,c=divmod(k["raw_slot"],16)
            maps[0][r][c]="MO(1)" if k["name"]=="Fn" else k["hid_usage"]
            for layer,changes in overrides.items():
                if k["name"] in changes:maps[int(layer)][r][c]=changes[k["name"]]
        header='#pragma once\n#include "quantum.h"\nstatic const uint16_t keymaps[2][6][16]={\n'
        for layer in maps:header+="{\n"+"\n".join("{"+",".join(row)+"}," for row in layer)+"\n},\n"
        (BUILD/"keymap.generated.h").write_text(header+"};\n")
        profile=json.loads((ROOT/"analysis/hall_board_profile.json").read_text())["keys"]
        assert len(profile)==67 and all(k["idle"]>k["pressed"]+100 for k in profile)
        header="#pragma once\n#define BAT68_HALL_KEYS 67\ntypedef struct {uint8_t slot,electrical;uint16_t idle,bottom;} bat68_hall_key_t;\nstatic const bat68_hall_key_t hall_keys[]={\n"
        for k in profile:header+=f"{{{k['raw_slot']},{k['electrical']},{k['idle']},{k['pressed']}}}, // {json.dumps(k['name'])}\n"
        (BUILD/"hall.generated.h").write_text(header+"};\n")
        sources += [qmk/p for p in ("quantum/action.c","quantum/action_layer.c","quantum/action_util.c","quantum/keymap_common.c","quantum/keycode_config.c","quantum/bitwise.c","quantum/led.c","quantum/logging/debug.c","tmk_core/protocol/host.c","tmk_core/protocol/report.c")]
        sources += [SRC/"keyboard.c",ROOT/"firmware/board/keymap_settings.c",ROOT/"firmware/board/sn34_flash.c",SDK/"Peripherals/Source/sn34f28x_hal_flash.c",SDK/"Peripherals/Source/sn34f28x_hal_flash_ex.c"]
        if args.keychron_he:
            from keychron_sources import prepare_keychron
            he_sources,he_includes,he_patches=prepare_keychron(ROOT,BUILD,qmk)
            sources += he_sources
            includes = he_includes + includes
            flags += ["-mfpu=fpv4-sp-d16","-mfloat-abi=softfp"]
    for include in includes:flags += ["-I",str(include)]
    if args.scan:sources += [SRC/"scan.c",ROOT/"firmware/board/bat68_scan.c",SDK/"Peripherals/Source/sn34f28x_hal_adc.c"]
    sources += [SDK/"Peripherals/Source"/n for n in (
        "sn34f28x_hal_rcc.c","sn34f28x_hal_iwdg.c","sn34f28x_hal_pcd.c","sn34f28x_ll_otgpe.c")]
    sources += [SDK/"Middlewares/Source/USB_Device/Core"/n for n in ("usbd_core.c","usbd_ctlreq.c","usbd_ioreq.c")]
    vendor_hid=SDK/"Middlewares/Source/USB_Device/Class/HID/usbd_hid.c"
    hid_text=vendor_hid.read_text()
    needle="HAL_Status_T           ret;"
    marker="static HAL_Status_T hid_update_desc(USBD_Class_t *pClass)"
    assert hid_text.count(marker)==1,"Review the SDK HID error-path initialization patch"
    before,body=hid_text.split(marker,1)
    assert needle in body[:1000],"Review the SDK HID local variable declaration"
    null_check="if (hep->pEp_desc->wMaxPacketSize == 0)"
    assert hid_text.count(null_check)==1,"Review the SDK OUT endpoint descriptor check"
    # Leave downloaded SDK sources intact. Repair the uninitialized error return
    # in a generated build copy and record the exact change in the manifest.
    patched_hid=BUILD/"vendor/usbd_hid.c"
    patched_hid.parent.mkdir(exist_ok=True)
    body=body.replace(needle,"HAL_Status_T           ret = HAL_ERROR;",1)
    body=body.replace(null_check,"if (pEp_desc->wMaxPacketSize == 0)",1)
    patched_hid.write_text(before+marker+body)
    sources += [patched_hid]
    objects=[]
    for i,source in enumerate(sources):
        obj=BUILD/f"{i:02}_{source.stem}.o"
        conf=["-include",str(SRC/"sn34f28x_hal_conf.h")] if source.suffix==".c" else []
        warnings=["-Wno-missing-field-initializers"] if source==patched_hid else []
        subprocess.run([str(llvm/"clang.exe"),*flags,*conf,*warnings,"-c",str(source),"-o",str(obj)],check=True)
        objects.append(str(obj))
    elf=BUILD/"native_usb.elf"
    subprocess.run([str(llvm/"clang.exe"),*flags,"-nostdlib","-fuse-ld=lld",*objects,
                    "-Wl,--gc-sections",f"-Wl,--defsym,BAT68_ROM_ORIGIN={0 if args.standalone else 0x30000}",
                    f"-Wl,-T,{SRC/'native.ld'}",f"-Wl,-Map,{BUILD/'native_usb.map'}","-o",str(elf)],check=True)
    binary=BUILD/"native_usb.bin"
    subprocess.run([str(llvm/"llvm-objcopy.exe"),"-O","binary",str(elf),str(binary)],check=True)
    with elf.open("rb") as stream:
        e=ELFFile(stream);symbols={s.name:s.entry.st_value for s in e.get_section_by_name(".symtab").iter_symbols()}
    manifest={"status":"BUILT_NOT_TESTED_NOT_FLASHED","purpose":"Complete source-built QMK keyboard application" if args.standalone else "Source-built independent QMK keyboard trial" if args.keyboard else "Source-built independent USB/ADC trial" if args.scan else "Source-built independent USB trial",
              "image_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"bytes":binary.stat().st_size,
              "rom_start":hex(symbols["__rom_origin"]),"ram_start":hex(symbols["__data_start"]),"ram_end":hex(symbols["__bss_end"]),
              "entry":hex(symbols["native_trial_entry"]),"vectors":hex(symbols["native_vectors"]),
              "adc_scan_included":args.scan,
              "qmk_keyboard_included":args.keyboard,"trial_milliseconds":None if args.standalone else args.trial_ms,"standalone":args.standalone,
              "cold_initialization_included":args.cold_init,
              "bringup_guard_enabled":args.bringup_guard,
              "ota_entry_method":"SDK HAL erase User footer page, then reset into retained Boot mapping" if args.keyboard else None,
              "original_application_inputs":[],"original_application_calls":[],
              "vendor_patches":[{"source":str(vendor_hid.relative_to(ROOT)),
                                  "changes":["Initialize hid_update_desc error return to HAL_ERROR",
                                             "Check the local OUT endpoint descriptor before storing its pointer"],
                                  "original_sha256":hashlib.sha256(vendor_hid.read_bytes()).hexdigest()}],
              "sources":[{"path":str(source.relative_to(ROOT)),"sha256":hashlib.sha256(source.read_bytes()).hexdigest()} for source in sources],
              "limits":["6KRO basic keyboard and two QMK layers; RGB driver pending" if args.standalone else "Standalone reset entry not yet installed; this image is entered through the bridge" if args.cold_init else "Clocks and board power GPIO are inherited from the application before the trial", "Hall normalization uses measured released references and initial factory bottom estimates" if args.keyboard else "QMK keyboard not included", "Hardware verification required for this build"]}
    if args.keyboard: manifest["qmk_commit"]=sha
    if args.keychron_he:
        manifest.update(keychron_he=True,qmk_repository="https://github.com/Keychron/qmk_firmware",keychron_patches=he_patches,
                        he_eeprom_banks=["0x7b000","0x7c000"],he_eeprom_bytes=3584,
                        travel_units="Keychron 0..240 normalized units; physical millimetres not calibrated",
                        hardware_verified=False)
        dependencies=set()
        for directory in (ROOT/"firmware/native",ROOT/"firmware/board",ROOT/"firmware/keychron",ROOT/"firmware/qmk_bridge",BUILD):
            dependencies.update(directory.rglob("*.h"))
        dependencies.add(SRC/"native.ld")
        dependencies.update((ROOT/"tools"/name for name in ("build_native_usb.py","keychron_sources.py")))
        manifest["build_inputs"]=[{"path":str(path.relative_to(ROOT)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(dependencies)]
    if args.standalone:
        payload=binary.read_bytes();assert len(payload)<(0x7b000 if args.keychron_he else 0x7d000)
        application=bytearray(0x7e000);application[:len(payload)]=payload
        application[-4:]=bytes.fromhex("5555aaaa")
        (BUILD/"bat68_native_app.bin").write_bytes(application)
        manifest.update(application_sha256=hashlib.sha256(application).hexdigest(),application_bytes=len(application),
                        application_file="bat68_native_app.bin",settings_pages=["0x7d000","0x7d200"],footer_page="0x7de00")
    (BUILD/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k!="sources"},indent=2))

if __name__=="__main__":main()
