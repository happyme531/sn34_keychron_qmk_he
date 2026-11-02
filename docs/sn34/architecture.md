# SN34 QMK platform

This fork is based on Keychron QMK `2025q3`, commit
`2b493ff95f2665db719b1e95c91babb5036e72f3`.

| Location | Responsibility |
| --- | --- |
| `platforms/sn34/sn34f28x` | Reset, clocks, timebase, watchdog, runtime, Flash and linker script |
| `tmk_core/protocol/sn34` | SONiX USB transport, QMK host reports and lifecycle adapters |
| `drivers/analog/adc_mux` | ADC/MUX sampling and complete-frame buffer ownership |
| `drivers/analog/keychron_he` | Sample mapping, travel conversion, calibration and Keychron integration |
| `drivers/eeprom/sn34*` | Cached EEPROM and CRC-protected two-bank commits |
| `drivers/led/ws2812_sn34.c` | SPI/DMA WS2812 output |
| `keyboards/<keyboard>` | QMK metadata, feature rules, board wiring, policy and keymaps |
| `util/sn34` | Packaging, independent flashing, Raw HID configuration and configurator export |
| `tests/sn34` | Offline ARM emulation and independent compatibility fixtures |

QMK's `quantum/main.c` owns the lifecycle. Keychron HE algorithms remain in
`keyboards/keychron/common/analog_matrix`; both stock keyboards and SN34 use
its existing Make source list, with SN34-specific scan/calibration adapters.
The ARM toolchain supplies newlib-nano. Its allocator grows through a bounded
`_sbrk` between BSS and the reserved stack region; there is no private libc or
statically reserved 32 KiB allocation arena.

## Build ownership

`qmk compile` owns the entire firmware build. The SN34 platform adds the chip
sources, external SDK paths, one Make rule for the build-local SDK fix, and C
preprocessing of the linker script. It runs no custom Python code and never
rewrites tracked sources. External paths are Make variables or `.sn34-local.mk`.

`keyboard.json` owns USB IDs/version, matrix dimensions, layout and LEDs.
`config.h` owns keyboard behavior, profile hotkeys, report queue capacity and
RGB defaults. Each keyboard's `profiles.c` owns its default HE profiles; the
read-only profile tables remain in Flash. `board/board_config.h` owns scan sizes
and the persistence ABI, with overridable chip defaults from
`platforms/sn34/include/sn34_defaults.h`. The linker script reads the same
headers. `board/wiring.h` contains inline
peripheral operations and ADC rank/scatter tables. `board/keys.inc` supplies
the one shared sample-to-matrix/calibration table; `hall_curve.inc` supplies
the measured response curve. These are ordinary maintained source files.

Common HID report definitions live in `tmk_core/protocol/usb_hid_reports.h` and
are included by both the existing USB descriptor implementation and SONiX.
No script extracts fragments from C source. Launcher wire IDs are mapped to
the actual QMK C enum through `rgb_protocol.inc`; optional export reads the
compiled mapping from the ELF.

## Runtime and persistence

The platform starts clocks, watchdog and GPIO. QMK's EEPROM initialization
loads the cache; HE matrix setup initializes fallback calibration and ADC.
Board housekeeping runs profile hotkeys, indicators and idle storage saves.
The board supplies the idle condition to the EEPROM driver. RGB indicators and
Raw HID configuration translation stay outside the peripheral/USB drivers.
The protocol handles USB queues, connection state and deferred reset requests.
Queue slots hold the actual maximum 32-byte report, with compile-time checks
for every supported report type; the endpoint's larger packet limit does not
inflate every queue entry. The EEPROM driver supplies the complete vendor API,
including initialization and capacity, without filtering QMK's source list.

Shared HE command handling owns packet bounds, parameter validation and live
profile updates. The SN34 Raw HID adapter owns the NKRO switch policy, RGB wire-ID
translation and a bounded read-only settings snapshot command. HE configuration
uses the ordinary Keychron handler without an SN34 input-activity gate. Matrix hooks,
frame consumption and travel conversion live
in one translation unit; the ADC producer and the optimized HE frame hook stay
separate. Calibration uses the board's maintained fallback endpoints.

Battle68 preserves its v36 matrix coordinates, physical Fn at `(0,0)`, EEPROM
banks and VIA compatibility date. The shared HE header defaults to the original
stock layout; SN34 overrides only the calibration start to reserve a separate
profile byte. v3 restores v1's non-overlapping payload layout. v1 banks need only
a header-version update; v2 banks shift calibration and subsequent VIA data
right in RAM before QMK initialization. Background commits leave the previous
bank intact until the new header is complete. Independent v1 and v2 fixtures
check these boundaries and all physical calibration endpoints. `sn34_test` exercises a different
3x5 matrix, 16 sampled slots, two phases, 12 switches, five LEDs and different
EEPROM banks. It is a synthetic test target, not a physical hardware port.

## Optional host tools

`device.py`, `export.py`, `package.py`, `backup.py` and `flash.py` are command
entry points. `firmware.py` reads a standard ELF for these tools and offline tests.
The old generator, build wrapper, object import and source-manifest framework
have been removed. Packaging is an explicit operation; it can preserve a
compatible settings backup and optionally wrap an external OEM updater.
The ordinary QMK `flash` target runs backup, packaging, SonixFlasherC and
post-reboot configuration verification. The firmware snapshot reads only the
logical EEPROM cache and checks its revision on each packet; it never exposes
arbitrary Flash reads or writes. See [flashing details](flashing.md).

See [build instructions](build.md), [porting notes](porting.md) and
[validation history](validation.md). Historical records describe the workflow
at their recorded revision; current commands are documented in `build.md`.
