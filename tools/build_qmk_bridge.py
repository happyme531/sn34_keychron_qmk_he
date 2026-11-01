# /// script
# dependencies = ["pefile", "capstone", "pyelftools"]
# ///
"""Build upstream QMK action/layer code with a pinned stock hardware backend.

No hardware I/O, no flashing. The output preserves original startup, ADC/USB,
configuration transport, and USB upgrade entry. The QMK key engine owns keyboard
reports. Its keymap and all state live in separately reserved RAM.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from elftools.elf.elffile import ELFFile
import pefile
from build_probe import thumb_branch,checksum
from hardware_registers import REGISTERS

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/"build/qmk_bridge"
SRC=ROOT/"firmware/qmk_bridge"
QMK=ROOT/"qmk_firmware"
SDK=ROOT/"analysis/sdk/sn34f28x_sdk_2.1.4"
SDK_HAL=SDK/"SDK/HAL"
BASE_SHA="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36"
UPSTREAM="180f394b489c238cb231c2bf8b080262155e03c0"

def run(args):subprocess.run([str(v) for v in args],check=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-trial",action="store_true",help="Embed the independently tested source-built USB trial")
    args=parser.parse_args()
    BUILD.mkdir(parents=True,exist_ok=True)
    sha=subprocess.check_output(["git","-C",str(QMK),"rev-parse","HEAD"],text=True).strip()
    assert sha==UPSTREAM,"QMK revision differs from reviewed sources"
    stock=(ROOT/"analysis/v118_rcdata_4000.bin").read_bytes()
    assert hashlib.sha256(stock).hexdigest()==BASE_SHA
    native_info=None;native_blob=b""
    if args.native_trial:
        native_dir=ROOT/"build/native_usb"
        native_info=json.loads((native_dir/"manifest.json").read_text())
        native_test=json.loads((native_dir/"test_results.json").read_text())
        native_blob=(native_dir/"native_usb.bin").read_bytes()
        native_sha=hashlib.sha256(native_blob).hexdigest()
        assert native_info["status"] in ("PASS_OFFLINE_NOT_FLASHED","HARDWARE_VERIFIED_NATIVE_USB") and native_test["status"]=="PASS_OFFLINE_NOT_FLASHED"
        assert native_sha==native_info["image_sha256"]==native_test["image_sha256"]
        if native_info.get("adc_scan_included"):
            scan_test=json.loads((native_dir/"scan_test_results.json").read_text())
            assert scan_test["status"]=="PASS_OFFLINE_NOT_FLASHED" and scan_test["image_sha256"]==native_sha
        if native_info.get("qmk_keyboard_included"):
            keyboard_test=json.loads((native_dir/"keyboard_test_results.json").read_text())
            assert keyboard_test["status"]=="PASS_OFFLINE_NOT_FLASHED" and keyboard_test["image_sha256"]==native_sha
            if native_info.get("ota_entry_method"):
                boot_test=json.loads((native_dir/"boot_test_results.json").read_text())
                assert boot_test["status"]=="PASS_OFFLINE_NOT_FLASHED" and boot_test["image_sha256"]==native_sha
                assert not any(stock[0x7de00:0x7dffc]),"OTA footer page overlaps original application data"
        assert native_info["rom_start"]=="0x30000" and not any(stock[0x30000:0x30000+len(native_blob)])
        assert 0x30000<=int(native_info["entry"],0)<0x30000+len(native_blob)
    (BUILD/"native_trial.generated.h").write_text(
        f"#pragma once\n#define BAT68_NATIVE_TRIAL_ENTRY {native_info['entry'] if native_info else '0'}u\n"+
        f"#define BAT68_NATIVE_TRIAL_BYTES {len(native_blob)}u\n")
    mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
    overrides=json.loads((SRC/"keymap_overrides.json").read_text())
    maps=[[["KC_NO"]*16 for _ in range(6)],[["KC_TRNS"]*16 for _ in range(6)]]
    for k in mapping:
        r,c=divmod(k["raw_slot"],16)
        maps[0][r][c]="MO(1)" if k["name"]=="Fn" else k["hid_usage"]
        for layer,changes in overrides.items():
            if k["name"] in changes:maps[int(layer)][r][c]=changes[k["name"]]
    header='#pragma once\n#include "quantum.h"\nstatic const uint16_t keymaps[2][6][16]={\n'
    for layer in maps:
        header+="{\n"+"\n".join("{"+",".join(row)+"}," for row in layer)+"\n},\n"
    header+="};\n"
    (BUILD/"keymap.generated.h").write_text(header)
    (BUILD/"hardware_registers.generated.h").write_text(
        "#pragma once\nstatic const uint32_t snapshot_addresses[]={\n"+
        "\n".join(f"0x{r['address']:08x}u, // {r['name']}" for r in REGISTERS)+"\n};\n")
    (BUILD/"hardware_registers.json").write_text(json.dumps(REGISTERS,indent=2))
    llvm=Path(os.environ.get("BAT68_LLVM",r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\ARM64\bin"))
    flags=["--target=arm-none-eabi","-mcpu=cortex-m4","-mthumb","-mfloat-abi=soft","-std=gnu11",
           "-ffreestanding","-fno-builtin","-fno-delete-null-pointer-checks","-fno-unwind-tables",
           "-fno-asynchronous-unwind-tables","-fno-stack-protector","-fno-pic","-fshort-enums",
           "-ffunction-sections","-fdata-sections","-Os","-Wall","-Wextra",
           "-Wno-unused-parameter","-Wno-type-limits","-Wno-sign-compare",
           "-include",str(SRC/"config.h")]
    includes=[SRC,ROOT/"firmware/board",BUILD,SDK/"Board",SDK_HAL/"Com",SDK_HAL/"Peripherals/Include",SDK_HAL/"Peripherals/Source",
              ROOT/"analysis/sdk/SONiX.SN34F2_DFP.2.0.4/Device/Include",ROOT/"reference/CMSIS_5/CMSIS/Core/Include",
              QMK/"quantum",QMK/"quantum/logging",QMK/"quantum/process_keycode",QMK/"quantum/keymap_extras",
              QMK/"quantum/nvm",QMK/"platforms",SRC/"platform",QMK/"tmk_core/protocol",ROOT/"firmware/probe",
              ROOT/"toolchains/newlib/extracted/usr/include/newlib"]
    includes += sorted({p.parent for p in (QMK/"quantum").rglob("*.h")}-set(includes))
    for path in includes:flags += ["-I",str(path)]
    sources=[QMK/p for p in ["quantum/action.c","quantum/action_layer.c","quantum/action_util.c",
              "quantum/keymap_common.c","quantum/keycode_config.c","quantum/bitwise.c","quantum/led.c",
              "quantum/logging/debug.c","tmk_core/protocol/host.c","tmk_core/protocol/report.c"]]
    sources += [SRC/"bridge.c",ROOT/"firmware/board/keymap_settings.c",ROOT/"firmware/board/sn34_flash.c",ROOT/"firmware/board/diagnostics.c",ROOT/"firmware/common/memory.c",SRC/"entry.S",ROOT/"firmware/probe/probe.c"]
    sources += [SDK_HAL/"Peripherals/Source"/s for s in ("sn34f28x_hal_flash.c","sn34f28x_hal_flash_ex.c","sn34f28x_hal_rcc.c")]
    objects=[]
    for i,source in enumerate(sources):
        obj=BUILD/f"{i:02}_{source.stem}.o"
        run([llvm/"clang.exe",*flags,"-c",source,"-o",obj])
        objects.append(obj)
    elf=BUILD/"bat68_qmk_bridge.elf"
    run([llvm/"clang.exe",*flags,"-nostdlib","-fuse-ld=lld",*objects,
         "-Wl,--gc-sections",f"-Wl,-T,{SRC/'bridge.ld'}",f"-Wl,-Map,{BUILD/'bat68_qmk_bridge.map'}",
         "-Wl,--undefined=qmk_init_entry","-o",elf])
    blob=BUILD/"qmk_extension.bin"
    run([llvm/"llvm-objcopy.exe","-O","binary",elf,blob])
    with elf.open("rb") as f:
        e=ELFFile(f)
        syms={s.name:s.entry.st_value for s in e.get_section_by_name(".symtab").iter_symbols()}
    payload=blob.read_bytes()
    assert len(payload)<0x18000 and not any(stock[0x18000:0x18000+len(payload)])
    out=bytearray(stock)
    out[0x18000:0x18000+len(payload)]=payload
    if native_blob:out[0x30000:0x30000+len(native_blob)]=native_blob
    changes=[]
    def patch(at,data,label):
        old=bytes(out[at:at+len(data)])
        out[at:at+len(data)]=data
        changes.append({"address":hex(at),"before":old.hex(),"after":data.hex(),"purpose":label})
    patch(0xeb60,thumb_branch(0xeb60,syms["probe_entry"]&~1),"Probe and QMK main-context task")
    # This stock sender runs in a timer interrupt; the gate only reads a mode
    # flag. QMK's engine runs in the main loop. Boot defaults to QMK.
    assert stock[0x13350:0x13354]==bytes.fromhex("10b53048")
    assert struct.unpack_from("<I",stock,0x13414)[0]==0x2000040b
    patch(0x13350,thumb_branch(0x13350,syms["stock_sender_gate"]&~1),"Gate stock reports only while explicitly in QMK mode")
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
    init=[i for i in md.disasm(stock[0x138f0:0x13920],0x138f0) if i.mnemonic=="bl" and i.op_str=="#0x40e8"]
    assert len(init)==1
    call=bytearray(thumb_branch(init[0].address,syms["qmk_init_entry"]&~1))
    second=struct.unpack_from("<H",call,2)[0]|0x4000
    struct.pack_into("<H",call,2,second)
    decoded=next(md.disasm(bytes(call),init[0].address))
    assert decoded.mnemonic=="bl"
    patch(init[0].address,call,"Initialize QMK RAM after original hardware initialization")
    assert out[:0x1c0]==stock[:0x1c0] and out[0x1d8:0x23c]==stock[0x1d8:0x23c]
    assert out[0x8000:0xba00]==stock[0x8000:0xba00]
    assert out[-4:]==bytes.fromhex("5555aaaa")
    assert not any(out[0x7d000:0x7d400]),"Default settings pages are not empty"
    (BUILD/"bat68_qmk_bridge_v118.bin").write_bytes(out)
    wrapper=bytearray((ROOT/"analysis/oem_updater_v118.exe").read_bytes())
    pe=pefile.PE(data=bytes(wrapper))
    resources={item.id:item.directory.entries[0].data.struct for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries if ty.id==10 for item in ty.directory.entries}
    loc=pe.get_offset_from_rva(resources[4000].OffsetToData)
    assert wrapper[loc:loc+len(stock)]==stock
    wrapper[loc:loc+len(out)]=out
    loc=pe.get_offset_from_rva(resources[4014].OffsetToData)
    wrapper[loc:loc+8]=f"{checksum(out):04X}".encode("utf-16le")
    pe=pefile.PE(data=bytes(wrapper))
    struct.pack_into("<I",wrapper,pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"),pe.generate_checksum())
    (BUILD/"BAT68_QMK_BRIDGE_v118.exe").write_bytes(wrapper)
    manifest={"status":"BUILT_NOT_TESTED_NOT_FLASHED","qmk_upstream_commit":sha,
              "implementation":"Upstream QMK action/layer/report core with stock scan and USB backend",
              "image_sha256":hashlib.sha256(out).hexdigest(),"checksum":f"0x{checksum(out):04X}",
              "extension_bytes":len(payload),"ram_start":hex(syms["__data_start"]),"ram_end":hex(syms["__bss_end"]),
              "patches":changes,"symbols":{k:hex(v) for k,v in syms.items() if k and (k.startswith("qmk_") or k in ("__data_load","__data_start","__data_end","__bss_start","__bss_end","layer_state","active_keymaps","matrix_state"))},
              "settings_pages":["0x7d000","0x7d200"],"default_keyboard_mode":"qmk",
              "open_backends":["QMK key engine","SONiX SDK v2.1.4 Flash HAL (source)","Bounded hardware diagnostics"],
              "remaining_original_backends":["Startup and clocks","ADC scanner","Hall calibration and travel","USB device stack","LED"],
              "native_usb_trial":None if native_info is None else {k:native_info[k] for k in ("image_sha256","bytes","rom_start","entry","ram_start","ram_end")},
              "limits":["6KRO keyboard reports", "set changes RAM; explicit save persists keymap", "OEM full-firmware update clears saved keymaps", "No full ChibiOS MCU port yet"]}
    (BUILD/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":
    try:main()
    except subprocess.CalledProcessError as error:raise SystemExit(error.returncode)
