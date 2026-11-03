# Building SN34 targets

Use the ordinary QMK build entry point, in Linux or WSL:

```sh
qmk compile -kb battle68 -km default
qmk compile -kb battle68 -km minimal
qmk compile -kb sn34_test -km default
qmk compile -kb langtu/boom68/wired -km default
```

Install QMK CLI and an ARM GNU toolchain on PATH. GCC 13.2.1 is the tested
compiler. The ARM toolchain must include newlib-nano headers, libraries,
`nano.specs` and `nosys.specs` (on Debian/Ubuntu, install `libnewlib-arm-none-eabi`
and `libnewlib-dev`). Supply SONiX SDK 2.1.4, DFP 2.0.4 and CMSIS Core
externally. Set the following environment/Make variables, or put them in the
ignored repository-root `.sn34-local.mk`:

```make
SN34_SDK_DIR := ../dependencies/sn34f28x_sdk_2.1.4/SDK/HAL
SN34_DFP_DIR := ../dependencies/SONiX.SN34F2_DFP.2.0.4/Device/Include
SN34_CMSIS_DIR := ../dependencies/CMSIS_5
```

Paths are relative to the repository root and must not contain spaces, as with
the surrounding QMK Make rules. Windows users run the same commands in WSL;
host tools below can run natively on Windows. `.sn34-local.json` and the old
SN34 build wrapper are no longer used.

Initialize the QMK HID macro headers if needed:

```sh
git submodule update --init --depth 1 lib/lufa
```

Firmware compilation has no SN34 Python stage. Board configuration, scan ranks,
calibration and response tables are maintained directly under each keyboard's
`board/` directory, with individual files inherited by keyboard variants.
The ordinary C preprocessor expands the linker script from
the same board constants used by C. Make applies the single SONiX HID fix to a
build-local copy; the external SDK is never modified.
Shared SN34F280 defaults are ordinary C headers, also listed as linker-script
dependencies. The complete cached EEPROM backend uses `EEPROM_DRIVER = vendor`;
its driver rules enable QMK initialization, and its configured `EEPROM_SIZE`
supplies the capacity. No generic EEPROM source is added and then excluded.
The HE core and matrix adapter alone use LTO so the hot loop can inline across
their public API without injecting platform source into the shared HE core.
Other QMK and SDK files keep their normal build settings.

Features use ordinary QMK rules and command-line overrides:

```sh
qmk compile -kb battle68 -km default -e RGB_MATRIX_ENABLE=no -e XINPUT_ENABLE=no -e SN34_OTA_ENABLE=no
```

Default outputs include `.build/battle68_default.elf` and
`.build/battle68_default.bin`. QMK also copies the BIN to the repository root.
`-e BUILD_DIR=/path/to/output` selects another build directory. There is no
second import directory, build manifest, source-hash gate or configurator
export in the compile path.
External SDK source paths are normalized before QMK derives object paths.
Different SN34 targets can share a `BUILD_DIR`, including concurrent builds;
their SDK objects and dependency files stay in separate target directories.

USB power follows the normal `usb.max_power` / `USB_MAX_POWER_CONSUMPTION`
setting (500 mA by default). With no polling override, HID keeps its existing
8 kHz high-speed / 1 kHz full-speed default. Explicit `usb.polling_interval` /
`USB_POLLING_INTERVAL_MS` settings accept 1, 2, 4, 8, 16, 32, 64 or 128 ms.
The SDK converts these exactly between high-speed exponents and full-speed
milliseconds; other values fail compilation. XInput keeps its own USB interval.

## Optional tools

Each tool uses uv script dependencies and can be run independently. Export
configuration files for the exact compiled RGB mapping with:

```sh
uv run util/sn34/export.py .build/battle68_default.elf
uv run util/sn34/device.py --keyboard battle68 status
uv run util/sn34/device.py --keyboard battle68 get --key A
```

Export writes `.build/battle68_default_config/sn34_via.json` and
`sn34_launcher.json`; `--output-dir` overrides that destination. The device
tool accepts unique key labels or `row,col` coordinates, and `--serial` selects
one of multiple attached keyboards. It uses only the standard Raw HID
interface. Settings save automatically after five seconds without key activity.
Any single QMK layout name is selected automatically. For keyboards with
multiple layouts, pass `--layout <name>` to export, device or test commands
(or set `SN34_LAYOUT`). Layout aliases are accepted as well.

The raw QMK BIN is the executable load image. Create the complete application
image, including the retained vendor footer, separately:

```sh
uv run util/sn34/package.py .build/battle68_default.elf
uv run util/sn34/package.py .build/battle68_default.elf --settings-backup /path/to/application-readback.bin --updater-template /path/to/oem_updater_v118.exe
```

Output defaults to `.build/battle68_default_release/`. Packaging checks ELF
memory bounds and the selected keyboard's USB identity. The optional external
updater must match `board/updater.json`. Settings preservation checks bank CRCs
against the compiled ELF's memory bounds and copies committed banks intact.
Startup compatibility is checked by the separate offline tests, not packaging.
SN34 v3 keeps the profile byte separate from calibration. v1 payloads remain
unchanged; v2 payloads migrate in RAM and commit through the background save
engine. The stock Keychron default layout remains unchanged. An OEM contract is
only needed when `--updater-template` is selected; ordinary application images
and independent flashing do not need it.

## Flashing

The independent path uses SonixFlasherC and the retained ISP Bootloader;
the official updater is optional. Configure `SN34_FLASHER`, then run:

```sh
qmk flash -kb battle68 -km default
```

This builds the ELF, snapshots live settings over Raw HID, creates the complete
application image with those settings, calls SonixFlasherC, and verifies the
complete settings cache after reboot. Older firmware without the snapshot
command needs an existing `--settings-backup` for the first upgrade or an
explicit `--reset-settings`. See [flashing instructions](flashing.md) for the
Windows/WSL setup, preparation without flashing, and migration limits.

## Offline tests

Tests consume the standard ELF directly, without copying or importing objects:

```sh
uv run tests/sn34/run.py
uv run tests/sn34/run.py --keymap minimal
uv run tests/sn34/run.py --keyboard sn34_test
uv run tests/sn34/run.py --keyboard langtu/boom68/wired
uv run tests/sn34/run.py --elf /path/to/battle68_default.elf
```

Logs and results go to `.build/sn34-tests/<target>/`. Measured reference data,
legacy EEPROM contracts and emulator helpers live under `tests/sn34/`; none
configure a build. Offline tests do not replace physical timing, typing,
power-cycle or USB-host validation.
The shared HE protocol tests call the common handler directly, checking profile
response bounds, rejected writes and immediate active-profile threshold changes
without relying on SN34's transport policy wrapper.
Linker contract tests compile small probes against the production linker script,
checking invalid bank, footer and RAM configurations. They run when
`arm-none-eabi-gcc` is on PATH and are skipped on host-only systems. To run them
separately in the ARM build environment:

```sh
uv run tests/sn34/test_compile_contracts.py
```

## Optional Launcher helper

The existing JSON-import compatibility helper remains under `util/sn34/launcher`
and does not participate in builds. Supply an externally installed signed Chrome:

```powershell
./util/sn34/launcher/open_launcher.ps1 -BrowserPath 'C:/path/to/chrome.exe' -Visible
```

On ARM64 Windows use native ARM64 Chrome. Import the JSON from the optional
export command. The helper accepts `-Keyboard`, `-Keymap` and `-Port`; browser
profiles and logs stay under `.build/launcher`. Its live web compatibility has
not been revalidated by this build cleanup.
