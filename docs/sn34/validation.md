# Refactor validation

Current independent flashing and calibration migration checks are recorded in
[standalone-flash-validation.json](standalone-flash-validation.json); physical
flashing and automatic configuration preservation are recorded in
[standalone-flash-hardware.json](standalone-flash-hardware.json). The
Launcher HE import regression and subsequent user confirmation are recorded in
[launcher-import-validation.json](launcher-import-validation.json). The
current workflow is documented in [flashing.md](flashing.md); earlier v2 layout
descriptions below are historical and superseded by SN34 v3.

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

## Review simplification (2026-11-03)

Shared HE command handling now owns profile-response bounds, parameter checks
and active-profile updates. The SN34 adapter retains held-key policy and RGB
wire-ID translation. Keyboard behavior and read-only default profiles belong to
each keyboard; chip defaults are shared with the linker. The complete vendor
EEPROM backend retains its cache, bank format and migration without source-list
filtering. Matrix hooks and frame consumption share one source file.

| Target | Previous BIN bytes | Current BIN bytes | Previous BSS bytes | Current BSS bytes |
| --- | ---: | ---: | ---: | ---: |
| Battle68 default | 89,328 | 89,712 | 70,424 | 61,656 |
| Battle68 minimal | 86,016 | 86,464 | 70,288 | 61,520 |
| Synthetic SN34 | 61,024 | 60,984 | 40,544 | 38,400 |

The default saves 8,768 bytes of RAM: 8,192 bytes from report slots sized for the
actual maximum 32-byte report, and 576 bytes from read-only default profiles.
Compile-time checks cover every supported report type. Default profiles move
into Flash; the net default BIN increase is 384 bytes.

Default and minimal each pass 18 unit tests, followed by eight default firmware
suites and the minimal hook suite. Synthetic passes 11 unit tests (one
production-only test skipped) and its firmware suite. The RGB/XInput/OTA-disabled
target passes 18 unit tests and checks of interface count, typing/release, Raw
HID and configurator export. Tests call the shared HE handler directly to check
profile-read guard bytes, invalid writes and live global thresholds.
Full stock `keychron/q1_he/ansi_encoder:keychron` and
`keychron/k2_he/ansi:keychron` builds also pass, including ELF linking and DFU
binary generation. Their required ChibiOS/printf submodules, FNV sources,
encoder driver and DFU suffix utility were populated for these checks.

All exported memory constants, profile sizes, key/calibration tables, USB report
descriptors and RGB protocol mappings match the preceding binaries. Standalone
configurator export and settings-preserving OEM updater packaging also pass.
Final images and results are recorded in
[simplification-validation.json](simplification-validation.json).
Builds use ordinary QMK commands; final verification selects the supported
`SKIP_GIT=yes` option to skip slow version probes in this Windows/WSL checkout.
No keyboard was flashed; physical behavior and timing were not retested.

## Architecture review cleanup (2026-11-03)

USB transport no longer depends on HE controller code, and report coalescing
uses QMK report IDs/types instead of fixed lengths and offsets. The HE adapter
owns controller recovery. The scan loop now calls the public HE API from its
own source file; LTO is limited to that adapter and the HE core. The core no
longer includes a platform frame implementation. Unused Raw HID indirection
and public command enums were removed, and thin private headers/Flash source
wrappers were consolidated. RGB animation selection uses QMK JSON metadata.

Board resources and linker preprocessing follow the keyboard hierarchy,
including transitive header dependencies. Host JSON metadata matches QMK for
the inherited target. Battle68 owns its historical migration; other boards
accept only explicitly declared legacy versions. The existing EEPROM v3 ABI,
calibration/key tables, profile sizes, report descriptors and configurator
exports are unchanged. Nonzero application origins are rejected explicitly.
PRIMASK-backed atomic blocks replace the global no-op atomic setting.

Default and minimal each pass 34 unit tests, plus eight default firmware suites
and the minimal hook suite. Synthetic passes 27 unit tests with one
production-only case skipped, followed by its firmware suite. The
RGB/XInput/OTA-disabled target passes 34 unit tests and a typing/release,
interface, Raw HID and export smoke check. Stock Q1 HE and K2 HE compile and
link successfully. Temporary inherited targets verify parent wiring, child
board configuration, nested linker dependencies and ordinary typing with
NKRO/mouse keys/extra keys/joystick disabled. A separate six-axis, 16-button,
hat-switch build verifies its 10-byte report, axis coalescing and ordered hat
and button transitions. The minimal fixture executes nested atomic blocks,
initially masked IRQs, early returns, breaks and FORCEON as real ARM code.

The default BIN decreases from 89,984 to 89,856 bytes and BSS from 61,656 to
61,600 bytes. Complete-loop instruction counts change from 6,421 to 6,485
when idle (+1.0%); all-key press, movement and release counts decrease slightly.
These are Unicorn instruction counts, not measured physical execution times.
Independent v1 settings banks remain byte-exact through application/OEM
packaging and independent flash preparation. No device was flashed.

Exact image hashes, baselines and results are recorded in
[review-cleanup-validation.json](review-cleanup-validation.json).
