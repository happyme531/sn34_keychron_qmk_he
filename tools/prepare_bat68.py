"""Generate board data, patched dependencies and the SN34 Make inputs."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from bat68_build_config import BuildPaths, ROOT, qmk_revision, write_if_changed
from bat68_board import generate_board
from bat68_patches import apply_series
from hall_curve import generate_hall_curve
from keychron_sources import prepare_keychron
from launcher_definition import generate_launcher_definition
from bat68_model import sync_keyboard_definition
from bat68_storage import generate_storage, LAYOUT


def prepare(paths):
    paths.validate()
    provenance = qmk_revision(paths.qmk)
    build, qmk, sdk = paths.build, paths.qmk, paths.sdk
    build.mkdir(parents=True, exist_ok=True)
    write_if_changed(build / "manifest.json", json.dumps({"status": "BUILDING_NOT_FLASHED"}) + "\n")
    # Invalidate the include first: Make must never reuse a stale source list
    # when a dependency check or patch fails in this preparation attempt.
    write_if_changed(build / "platform_sources.mk", "$(error BAT68 preparation incomplete; rerun tools/build_bat68.py)\n")
    generate_board(ROOT, build)
    generate_storage(build)
    sync_keyboard_definition(qmk, check=True)
    generate_hall_curve(ROOT, build)
    _, _, patches = prepare_keychron(ROOT, build, qmk)
    hid = "Middlewares/Source/USB_Device/Class/HID/usbd_hid.c"
    sdk_files, sdk_record = apply_series(sdk, [hid], build / "vendor/sonix", ROOT / "patches/sonix")
    write_if_changed(build / "vendor/usbd_hid.c", sdk_files[hid].read_bytes())
    patches.append(sdk_record)

    descriptors = (qmk / "tmk_core/protocol/usb_descriptor.c").read_text(encoding="utf-8")
    start = descriptors.index("// clang-format off")
    end = descriptors.index("#ifdef CONSOLE_ENABLE", start)
    preamble = ('#pragma once\n#include "report.h"\n#include "usb_descriptor_common.h"\n'
                '#define __INCLUDE_FROM_USB_DRIVER\n#define __INCLUDE_FROM_HID_DRIVER\n'
                '#include "lib/lufa/LUFA/Drivers/USB/Class/Common/HIDReportData.h"\n'
                'typedef uint8_t USB_Descriptor_HIDReport_Datatype_t;\n')
    write_if_changed(build / "reports.generated.h", preamble + descriptors[start:end])
    # QMK owns version.h. VIA's explicit compatibility tag is generated from
    # storage.json; include search order must not decide persistence validity.
    obsolete=(build/"version.h").resolve()
    if obsolete.parent==build.resolve() and obsolete.is_file() and obsolete.read_bytes().startswith(b'#pragma once\n#define QMK_BUILDDATE "'):
        obsolete.unlink()
    generate_launcher_definition(ROOT, build, qmk, newlib=paths.newlib)

    # Only platform/board/SDK additions live here. QMK itself owns the core
    # source selection, feature flags and keymap selection through rules.mk.
    sources = [ROOT / "firmware/native" / name for name in
               ("startup.S", "clock.c", "timebase.c", "runtime.c", "scan.c")]
    sources += [ROOT / "firmware" / name for name in
                ("common/memory.c", "common/ctype.c", "board/bat68_scan.c", "board/sn34_flash.c", "keychron/eeprom.c")]
    sources += [ROOT / "firmware/qmk" / name for name in
                ("main.c", "runtime.c", "battle68.c", "matrix.c", "host.c", "he.c", "storage.c", "indicators.c", "protocol.c",
                 "raw_hid.c", "diagnostics.c", "rgb.c", "xinput_usb.c")]
    he = build / "vendor/keychron_he"
    sources += [he / name for name in
                ("analog_matrix.c", "profile.c", "action_regular_trigger.c", "action_rapid_trigger.c", "action_okmc.c",
                 "action_toggle.c", "action_socd.c", "game_controller_common.c", "action_joystick.c", "action_xinput.c",
                 "sqrt.c", "nkro.c", "keychron_raw_hid.c")]
    sources += [sdk / "Peripherals/Source" / name for name in
                ("sn34f28x_hal_gpio.c", "sn34f28x_hal_scu.c", "sn34f28x_hal_adc.c", "sn34f28x_hal_flash.c",
                 "sn34f28x_hal_flash_ex.c", "sn34f28x_hal_rcc.c", "sn34f28x_hal_iwdg.c", "sn34f28x_hal_pcd.c",
                 "sn34f28x_ll_otgpe.c", "sn34f28x_hal_spi.c", "sn34f28x_hal_dma.c")]
    sources += [sdk / "Middlewares/Source/USB_Device/Core" / name for name in
                ("usbd_core.c", "usbd_ctlreq.c", "usbd_ioreq.c")]
    sources += [build / "vendor/usbd_hid.c", build / "vendor/via.c"]
    includes = [build, build / "vendor", ROOT / "firmware", ROOT / "firmware/qmk", ROOT / "firmware/native",
                ROOT / "firmware/board", ROOT / "firmware/keychron", he, qmk,
                ROOT / "firmware/qmk/platform", qmk / "keyboards/keychron/common", sdk / "Com", sdk.parent.parent / "Board",
                sdk / "Peripherals/Include", sdk / "Peripherals/Source", sdk / "Middlewares/Include",
                sdk / "Middlewares/Source/USB_Device/Core", sdk / "Middlewares/Source/USB_Device/Class/HID",
                paths.dfp, paths.cmsis / "CMSIS/Core/Include", paths.newlib]
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(f"Missing source: {path}")
    compiler = os.environ.get("BAT68_CC", "arm-none-eabi-gcc")
    compiler_version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
    config = {"source_roots": paths.serialized_roots(), **provenance, "compiler": compiler_version,
              "qmk_build_dir": paths.label(Path(os.environ.get("BAT68_QMK_BUILD_DIR", str(build/"qmk")))),
              "wsl_distribution": os.environ.get("WSL_DISTRO_NAME", "Ubuntu")}
    write_if_changed(build / "build_config.json", json.dumps(config, indent=2) + "\n")
    write_if_changed(build / "patches.json", json.dumps(patches, indent=2) + "\n")
    relative = lambda path: os.path.relpath(path, qmk).replace("\\", "/")
    make = "BAT68_EXTRA_SRC := " + " ".join(map(relative, sources)) + "\n"
    make += "BAT68_EXTRA_INC := " + " ".join(map(relative, includes)) + "\n"
    make += f"BAT68_CODE_KIB := {LAYOUT.code_limit//1024}\n"
    write_if_changed(build / "platform_sources.mk", make)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    prepare(BuildPaths.environment())


if __name__ == "__main__":
    main()
