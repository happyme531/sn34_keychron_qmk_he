# SN34 QMK firmware

This fork of [Keychron QMK](https://github.com/Keychron/qmk_firmware) adds a
SONiX SN34F280 platform and wired Hall-effect keyboard ports. HE processing
reuses Keychron's common algorithms; firmware builds use ordinary QMK commands.

## Keyboards

| QMK target | Hardware | Notes |
| --- | --- | --- |
| [`battle68`](keyboards/battle68/readme.md) | 67 Hall switches, RGB and status LEDs | EEPROM format v3; recorded flashing and Launcher import checks |
| [`langtu/boom68/wired`](keyboards/langtu/boom68/wired/readme.md) | 67 Hall switches, rotary encoder/button and 94 RGB pixels | Wired BOOM68 only; EEPROM format v4; board-specific first installation |
| `sn34_test` | Synthetic 3x5 matrix | Compile/emulation coverage only; not a physical keyboard |

The physical ports provide adjustable actuation, rapid trigger, HE profiles,
advanced key actions, RGB Matrix, VIA keymap/macros/RGB configuration,
Keychron Launcher HE configuration, and
optional HID joystick/XInput reports. The original keyboards and QMK
documentation remain in the tree.

The current code has build and offline regression coverage. Earlier hardware
checks apply to the firmware recorded in [validation notes](docs/sn34/validation.md);
the latest cleanup has not been flashed as part of those checks.

## Build and test

Build in Linux or WSL with QMK CLI and an ARM GNU toolchain including
newlib-nano. Optional tools and tests use [uv](https://docs.astral.sh/uv/).
Supply SONiX SDK 2.1.4, DFP 2.0.4 and CMSIS Core externally; versions and SDK
provenance are recorded in [dependencies.json](platforms/sn34/dependencies.json).

Put their paths in an ignored repository-root `.sn34-local.mk`:

```make
SN34_SDK_DIR := ../dependencies/sn34f28x_sdk_2.1.4/SDK/HAL
SN34_DFP_DIR := ../dependencies/SONiX.SN34F2_DFP.2.0.4/Device/Include
SN34_CMSIS_DIR := ../dependencies/CMSIS_5
```

Then, from this checkout:

```sh
git submodule update --init --depth 1 lib/lufa
qmk compile -kb battle68 -km default
qmk compile -kb langtu/boom68/wired -km default
uv run tests/sn34/run.py --keyboard battle68
uv run tests/sn34/run.py --keyboard langtu/boom68/wired
```

There is no separate prepare, generate or object-import command. Different
targets can share the build directory. See [build instructions](docs/sn34/build.md)
for dependencies, optional features, USB polling settings and the synthetic target.

## Configure

Export definitions for the exact compiled firmware, then import the resulting
JSON in VIA or the Keychron Launcher JSON-import page:

```sh
uv run util/sn34/export.py .build/battle68_default.elf
uv run util/sn34/export.py .build/langtu_boom68_wired_default.elf --keyboard langtu/boom68/wired
```

Output goes to `<target>_config/` beside the ELF. Host tools default to
`battle68`; pass `--keyboard` for another board. Layout names are unrestricted;
use `--layout <name>` when a keyboard defines several layouts.

The Raw HID tool can inspect or configure a connected board:

```sh
uv run util/sn34/device.py --keyboard battle68 status
uv run util/sn34/device.py --keyboard langtu/boom68/wired get --key A
```

Settings save automatically after five seconds without key activity. Exported
HE travel units do not establish measured physical millimetres. The optional
[Launcher compatibility helper](docs/sn34/build.md#optional-launcher-helper)
addresses the recorded JSON-import macro issue; the live website may change.

## Flash

Read [flashing instructions](docs/sn34/flashing.md) and the selected keyboard's
notes before installation. The independent path uses the
[SN34-enabled SonixFlasherC fork](https://github.com/happyme531/SonixFlasherC).
Build the flasher separately; the flasher and official updater EXEs are external.

After configuring `SN34_FLASHER`, a compatible firmware already running on the
keyboard can be upgraded with `qmk flash`. The workflow backs up current
settings, builds a complete application image and verifies settings after reboot.
BOOM68's first installation from OEM V1.10 uses a different ISP handoff.

**The QMK executable-only BIN is not the complete flashable application.** Use
the host tools to include settings banks and the retained bootloader footer.
Only the selected board's current EEPROM format is accepted; older formats
are not converted. First installation or an incompatible settings format
requires `--reset-settings` and subsequent reconfiguration.

## Development

- [Build, tools and tests](docs/sn34/build.md)
- [Flashing and recovery](docs/sn34/flashing.md)
- [Architecture and upstream integration](docs/sn34/architecture.md)
- [Add another keyboard](docs/sn34/porting.md)
- [Validation scope and dated hardware records](docs/sn34/validation.md)
- [QMK contributing guidelines](docs/contributing.md)

The Keychron baseline is recorded in [upstream.json](platforms/sn34/upstream.json).
This repository uses the [GNU General Public License v2.0](LICENSE), with
component-specific notices retained in their source files.
