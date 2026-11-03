# SN34 architecture

The Keychron QMK baseline is commit
`2b493ff95f2665db719b1e95c91babb5036e72f3`, recorded in
[`upstream.json`](../../platforms/sn34/upstream.json).

| Location | Responsibility |
| --- | --- |
| `platforms/sn34/sn34f28x` | Startup, clocks, watchdog, timebase, libc hooks, Flash and linker script |
| `tmk_core/protocol/sn34` | SONiX USB classes, host report queues and QMK protocol lifecycle |
| `drivers/analog/adc_mux` | ADC/MUX scanning and complete-frame buffer ownership |
| `drivers/analog/keychron_he` | Sample-to-matrix mapping, travel conversion, fallback calibration and HE configuration adapter |
| `drivers/eeprom/sn34*` | EEPROM cache and CRC-protected two-bank commits |
| `drivers/led/ws2812_sn34.c` | SPI/DMA WS2812 output |
| `keyboards/<keyboard>` | Metadata, features, wiring, default profiles, keymaps and product policy |
| `util/sn34` | Configuration, export, packaging, settings snapshots and flashing |
| `tests/sn34` | ARM emulation and independent board/reference fixtures |

## Build ownership

`qmk compile` owns the build. The platform adds startup/SDK sources, applies
the HID SDK patch to a build-local copy and preprocesses the linker script.
External SDK paths are normalized before QMK derives target-local object paths,
so different targets can build concurrently in the same output directory.

`keyboard.json` defines identity, matrix dimensions, layouts, LEDs and RGB
animations. `config.h` defines board behavior and optional overrides.
`rules.mk` selects features and drivers; VIA enables Raw HID automatically.
`post_rules.mk` applies Bootmagic policy after QMK feature selection and loads
the optional RGB driver. `profiles.c` contains read-only default HE profiles.

`board/board_config.h` defines scan sizes and the storage contract, using
shared chip defaults from `platforms/sn34/include/sn34_defaults.h`.
The linker reads the same headers and records transitive dependencies.
Individual board files can be inherited through QMK's keyboard hierarchy;
the most specific board include directory is searched first.

`board/wiring.h` supplies inline peripheral operations and ADC rank/scatter
tables. `keys.inc` defines the shared sample-to-matrix/calibration table, and
`hall_curve.inc` defines the board's response curve. These are maintained
sources; provenance and measurement limits belong in the board documentation.

Keychron's HE source list remains shared with the stock boards. Its hardware
source selectors choose SN34 scan, calibration and USB adapters. Only the
matrix adapter and common HE core use LTO, retaining hot-loop inlining through
the public API. newlib-nano supplies libc with a bounded heap below the stack.

## Runtime

QMK's `quantum/main.c` owns the lifecycle. Platform setup starts clocks,
watchdog and GPIO; EEPROM initialization loads the current-format cache;
matrix setup prepares fallback calibration and starts ADC scanning.
The scanner publishes complete frames with buffer leasing, using PRIMASK-backed
atomic blocks to protect ownership transitions.

Board housekeeping calls `sn34_he_task()` for profile hotkeys and idle saves,
then performs board-specific indication work. Key/RGB hooks respect user-hook
return values. Mixed Hall/digital boards can implement `sn34_matrix_scan_extra()`
for debounced digital inputs even when no new ADC frame is available.

The USB transport owns queues, connection state and deferred reset requests.
The HE adapter supplies controller recovery. Queues default to 256 slots with
96 reserved for input bursts; a board may override these values. Report slots
are 32 bytes, with compile-time checks against supported QMK report types.
USB power and explicit HID polling settings follow normal QMK configuration;
see [build.md](build.md) for the supported intervals and defaults.

Common HID report definitions are shared in
`tmk_core/protocol/usb_hid_reports.h`. Launcher RGB wire IDs are translated by
the HE adapter; optional export reads the compiled mapping from the ELF.

## Persistence

The EEPROM cache holds QMK, HE and VIA settings. Background saves start after
five seconds without actuated input and write at most one Flash page per step.
The previous committed bank stays valid until the new bank's CRC-protected
header is complete. The linker rejects overlapping banks and invalid code,
footer, heap and stack bounds.

Each board accepts only its current EEPROM magic, version and size. Invalid
or incompatible banks initialize defaults. No legacy-format acceptance bitmap,
payload conversion or board migration callback is present. Current-format
settings snapshots and committed banks are preserved without conversion.
Changing the persistent layout requires a version change and reconfiguration;
the firmware and host tools enforce the same version contract.

SN34 reserves a distinct selected-profile byte before calibration, through the
common HE calibration-offset hook. The stock Keychron default layout remains
unchanged. The VIA compatibility date is stable across rebuilds so a changed
build timestamp does not reset current-format keymaps or macros.

## Host tools and upstream integration

Host tools read the ordinary ELF and maintained JSON metadata. Their JSON
reader follows this checkout's inheritance/layout merging while keeping
Windows USB tools independent of a QMK CLI installation. A shared selector
accepts arbitrary layout names/aliases; multiple layouts require `--layout`
or `SN34_LAYOUT`. Config/rules interpretation stays in QMK.

Packaging checks ELF bounds and copies matching settings banks intact. The
retained bootloader requires User-ROM application offset zero and a valid
footer. `qmk flash` delegates to the host backup/package/flash workflow;
see [flashing.md](flashing.md) for installation and recovery.

Keep platform/board changes separate from general HE, calibration, joystick,
Raw HID and VIA corrections when following upstream. The common conversion
hook, hardware source selectors, Fn-layer condition and calibration offset
are the main HE integration points. See [porting.md](porting.md) for a new board
and [validation.md](validation.md) for test scope and dated hardware evidence.
