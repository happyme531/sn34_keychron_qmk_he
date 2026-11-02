# Building SN34 targets

Use the ordinary QMK build entry point, in Linux or WSL:

```sh
qmk compile -kb battle68 -km default
qmk compile -kb battle68 -km minimal
qmk compile -kb sn34_test -km default
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
`board/` directory. The ordinary C preprocessor expands the linker script from
the same board constants used by C. Make applies the single SONiX HID fix to a
build-local copy; the external SDK is never modified.

Features use ordinary QMK rules and command-line overrides:

```sh
qmk compile -kb battle68 -km default -e RGB_MATRIX_ENABLE=no -e XINPUT_ENABLE=no -e SN34_OTA_ENABLE=no
```

Default outputs include `.build/battle68_default.elf` and
`.build/battle68_default.bin`. QMK also copies the BIN to the repository root.
`-e BUILD_DIR=/path/to/output` selects another build directory. There is no
second import directory, build manifest, source-hash gate or configurator
export in the compile path.

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
Firmware converts v1 settings to the restored stock HE layout in RAM and
commits a v2 bank only through the ordinary background save engine.
Synthetic targets have no production packaging contract.

## Offline tests

Tests consume the standard ELF directly, without copying or importing objects:

```sh
uv run tests/sn34/run.py
uv run tests/sn34/run.py --keymap minimal
uv run tests/sn34/run.py --keyboard sn34_test
uv run tests/sn34/run.py --elf /path/to/battle68_default.elf
```

Logs and results go to `.build/sn34-tests/<target>/`. Measured reference data,
legacy EEPROM contracts and emulator helpers live under `tests/sn34/`; none
configure a build. Offline tests do not replace physical timing, typing,
power-cycle or USB-host validation.

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
