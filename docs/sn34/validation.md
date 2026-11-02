# Refactor validation

This is the historical validation record before custom diagnostics were removed.
For the current source tree, see [the cleanup validation](cleanup-validation.md).

Tested code commit: `38ba288d321ec1d5c6c7abfbcee03d47acd16215`.
The tests were run from an independent, clean Git checkout with no preceding
build directory. SDK, DFP, CMSIS and toolchain locations were supplied as ignored
local configuration. No source overlay or second QMK tree was used.

| Target | Code bytes | Offline validation | Compile objects | Recorded inputs |
| --- | ---: | --- | ---: | ---: |
| Battle68 default | 85,704 | All eight firmware groups | 113 | 577 |
| Battle68 minimal | 82,408 | Independent board/user hooks | 111 | 569 |
| Synthetic SN34 target | 56,008 | Key input, persistence and omitted interfaces | 100 | 485 |

Twenty host/model/build contract tests also passed. The three builds have no
shared object files, and every object is within its own keyboard/keymap build
directory. Owned source inputs resolve inside that checkout; external inputs
are restricted to the explicitly configured dependency roots. Keychron HE/VIA
compile directly from their tracked, patched source files.

The synthetic target exercises a 3x5 matrix, 16 sample slots, two scan phases,
12 switches, five independently described LEDs and different EEPROM banks.
RGB, XInput, diagnostics and application OTA interfaces are disabled; the
remaining three USB interfaces and Raw HID routing were executed in emulation.

The default regression includes the frozen v36 keymap, calibration defaults,
LED mapping and persistent-format contracts, USB/backpressure and lifecycle
behavior, startup, ADC scatter/mux reference results, and interrupted Flash
commits. OEM scan/Boot references are captured data, not bundled executables.

Packaging was tested with the controlled v36 settings fixture and an external
OEM updater template. New-firmware startup preserved the complete expected
cache, the application resource matched the packaged image, and the firmware
word checksum and PE checksum were verified. No updater template is stored in
the repository.

Default code SHA-256:
`9ace99877f457c9589ab2ec06df26a5a3adb74f83578d723dcbfa7b7b846fe5f`.

These are offline results. Physical cold boot, key feel/noise, USB hosts,
lighting waveforms, power loss and real OTA require a separate hardware run.
Hardware flashing and acceptance are deferred by the user's delivery choice;
the connected keyboard's existing firmware was retained.

The optional Launcher helper was restored after the tested code commit.
Its dependency-locked entry point, Python/JavaScript/PowerShell syntax and
board-specific script rendering were checked offline. The live Launcher and
USB interaction were not exercised in this delivery. Later source-formatting
changes do not change the tested firmware code.

All three final main-worktree targets were rebuilt after those updates.
Their BIN images match the verified clean-checkout images byte for byte outside
QMK's 20-byte generated build-time string. Exact hashes, times and offsets are
recorded in [the final rebuild comparison](rebuild-validation.json).

## Configuration and Make refactor, 2026-11-02

Review items 1–5 were implemented on the current worktree. Standard QMK metadata
now owns USB identity, matrix dimensions, physical layout and RGB LED mapping;
default keymaps are ordinary C files. Make owns feature/backend selection and
the incremental generation rules. HE, EEPROM and indicator services use QMK
matrix, EEPROM and keyboard hooks. The EEPROM format and frozen compatibility
fixtures were retained.

All 23 host/model/build tests passed. Battle68 default passed eight firmware
groups, minimal passed its keyboard/user-hook group, and the synthetic target
passed its firmware group. Final input hashes and test-image hashes were checked
for all three builds. Default/minimal/synthetic code sizes are respectively
81,680 / 78,376 / 54,520 bytes.

A separate ordinary QMK build accepted command-line RGB/XInput/OTA disables
without editing board JSON. It exposed three USB interfaces and passed emulated
typing, release and Raw HID identity checks. No-op generation preserved every
SN34 output/stamp timestamp; dry-run left a missing generated header absent,
while real Make restored it without repatching the SDK or rewriting tracked
sources. Configurator JSON export was not required for compilation.

The original Keychron HE Make fragment's default source list, include path and
flags expanded identically before and after parameterizing its adapters. Full
OEM ChibiOS firmware compilation was not run because those submodule sources
are not populated in this checkout.

Exact images and results are recorded in [refactor-validation.json](refactor-validation.json).
These checks are offline; no keyboard was flashed for this refactor.

## Python/build cleanup

The current firmware entry point is ordinary `qmk compile`; optional tools and
offline tests read the resulting ELF directly. Earlier records retain the
commands and artifact structure used at their recorded revision. See
[the current build instructions](build.md).

The Python/build cleanup results are recorded in
[python-cleanup-validation.json](python-cleanup-validation.json).

## Architecture and runtime cleanup, 2026-11-03

The shared Keychron HE EEPROM header now matches upstream commit `2b493ff9`
exactly. SN34 v1 banks are converted in RAM to the stock byte layout before
QMK/VIA initialization and committed as v2 through the existing background
engine. Full-cache comparison, interruption during conversion save, and a
fresh v2 startup passed. The original stock overlap between the profile index
and the first calibration byte is deliberately retained.

newlib-nano supplies allocation, memory functions, character classes and other
C library functions. The platform supplies bounded `_sbrk`; the private 32 KiB
arena and custom libc implementations were removed. Heap reuse, allocation
failure, break overflow/underflow and memory alignment checks passed. All owned
firmware compiles with `-Werror`; exceptions apply only to SONiX source files.
SDK warnings and newlib nosys warnings for unsupported host I/O remain visible.

USB uses ordinary QMK Raw HID dispatch. Board hooks own RGB indicators and
supply the HE idle condition for storage. Derived addresses replace duplicated
constants, unused linker exports and the extra bootloader selector were removed,
and revision tracking replaces explicit save requests. Packaging reads memory
bounds from the ELF and copies CRC-valid banks without test/emulator imports.
Startup emulation remains an independent regression step.

| Target | Previous BIN bytes | Current BIN bytes | Previous static RAM | Current static RAM |
| --- | ---: | ---: | ---: | ---: |
| Battle68 default | 81,680 | 89,328 | 103,968 | 71,616 |
| Battle68 minimal | 78,376 | 86,016 | 103,784 | 71,440 |
| Synthetic SN34 | 54,520 | 61,024 | 73,536 | 41,184 |

The default passed 15 unit tests and eight firmware suites. Minimal passed its
15 unit tests and board/user-hook suite. The synthetic target passed eight unit
tests (one production-only test skipped) and its firmware suite. A separate
RGB/XInput/OTA-disabled Battle68 build passed 15 unit tests plus interface,
typing/release, Raw HID and export checks. Final suite image hashes match their
BIN files. Standalone export and settings-preserving OEM updater packaging
passed. The repository-root BIN matches the default build.

Exact images and checks are recorded in
[architecture-cleanup-validation.json](architecture-cleanup-validation.json).
The task-start source snapshot and review patch are under
`.build/architecture-cleanup-before/` and `.build/architecture-cleanup/changes.patch`.
No keyboard was flashed. Full stock ChibiOS builds remain untested because the
submodule sources are not populated in this checkout.
