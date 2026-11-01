"""Generate target data and a patched copy of the external SDK HID class."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from build_config import BuildPaths, ROOT, board_directory, keyboard_name, qmk_revision, write_if_changed
from board import generate_board
from patches import apply_series
from hall_curve import generate_hall_curve
from launcher_definition import generate_launcher_definition
from model import sync_keyboard_definition
from model import load_board
from hardware import generate_hardware
from storage import generate_storage, LAYOUT


def prepare(paths):
    paths.validate()
    provenance = qmk_revision(paths.qmk)
    build, qmk, sdk = paths.build, paths.qmk, paths.sdk
    build.mkdir(parents=True, exist_ok=True)
    write_if_changed(build / "manifest.json", json.dumps({"status": "BUILDING_NOT_FLASHED"}) + "\n")
    write_if_changed(build / "platform_sources.mk", "$(error SN34 preparation incomplete; rerun util/sn34/build.py)\n")
    generate_board(ROOT, build)
    generate_hardware(load_board(), build)
    generate_storage(build)
    sync_keyboard_definition(qmk, check=True)
    generate_hall_curve(ROOT, build)
    hid = "Middlewares/Source/USB_Device/Class/HID/usbd_hid.c"
    sdk_files, sdk_record = apply_series(sdk, [hid], build / "vendor/sonix", ROOT / "util/sn34/patches/sonix")
    descriptors = (qmk / "tmk_core/protocol/usb_descriptor.c").read_text(encoding="utf-8")
    start = descriptors.index("// clang-format off")
    end = descriptors.index("#ifdef CONSOLE_ENABLE", start)
    preamble = ('#pragma once\n#include "report.h"\n#include "usb_descriptor_common.h"\n'
                '#define __INCLUDE_FROM_USB_DRIVER\n#define __INCLUDE_FROM_HID_DRIVER\n'
                '#include "lib/lufa/LUFA/Drivers/USB/Class/Common/HIDReportData.h"\n'
                'typedef uint8_t USB_Descriptor_HIDReport_Datatype_t;\n')
    write_if_changed(build / "reports.generated.h", preamble + descriptors[start:end])
    generate_launcher_definition(ROOT, build, qmk, newlib=paths.newlib)
    sources = [sdk / "Peripherals/Source" / name for name in
               ("sn34f28x_hal_gpio.c", "sn34f28x_hal_scu.c", "sn34f28x_hal_adc.c", "sn34f28x_hal_flash.c",
                "sn34f28x_hal_flash_ex.c", "sn34f28x_hal_rcc.c", "sn34f28x_hal_iwdg.c", "sn34f28x_hal_pcd.c",
                "sn34f28x_ll_otgpe.c", "sn34f28x_hal_spi.c", "sn34f28x_hal_dma.c")]
    sources += [sdk / "Middlewares/Source/USB_Device/Core" / name for name in ("usbd_core.c", "usbd_ctlreq.c", "usbd_ioreq.c")]
    sources += [sdk_files[hid]]
    includes = [build, ROOT / "platforms/sn34/include", ROOT / "drivers/eeprom", ROOT / "drivers/led",
                ROOT / "drivers/analog/keychron_he", ROOT / "tmk_core/protocol/sn34", board_directory(),
                qmk / "keyboards/keychron/common/analog_matrix", qmk / "keyboards/keychron/common", qmk,
                sdk / "Com", sdk.parent.parent / "Board", sdk / "Peripherals/Include", sdk / "Peripherals/Source",
                sdk / "Middlewares/Include", sdk / "Middlewares/Source/USB_Device/Core",
                sdk / "Middlewares/Source/USB_Device/Class/HID", paths.dfp, paths.cmsis / "CMSIS/Core/Include", paths.newlib]
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(f"Missing source: {path}")
    compiler = os.environ.get("SN34_CC", "arm-none-eabi-gcc")
    config = {"source_roots": paths.serialized_roots(), **provenance, "keyboard": keyboard_name(),
              "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
              "qmk_build_dir": paths.label(Path(os.environ.get("SN34_QMK_BUILD_DIR", str(build / "qmk")))),
              "wsl_distribution": os.environ.get("WSL_DISTRO_NAME", "Ubuntu")}
    write_if_changed(build / "build_config.json", json.dumps(config, indent=2) + "\n")
    write_if_changed(build / "patches.json", json.dumps([sdk_record], indent=2) + "\n")
    relative = lambda path: os.path.relpath(path, qmk).replace("\\", "/")
    make = "SN34_EXTRA_SRC := " + " ".join(map(relative, sources)) + "\n"
    make += "SN34_EXTRA_INC := " + " ".join(map(relative, includes)) + "\n"
    make += f"SN34_CODE_KIB := {LAYOUT.code_limit//1024}\n"
    write_if_changed(build / "platform_sources.mk", make)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    prepare(BuildPaths.environment())

