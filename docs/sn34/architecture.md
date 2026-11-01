# SN34 QMK platform

This fork starts from Keychron QMK `2025q3`, commit
`2b493ff95f2665db719b1e95c91babb5036e72f3`. The import commit preserves the
development workspace sources. Historical probe, bridge and standalone trial
implementations are available in that commit; they are not build dependencies.

## Ownership

| Location | Responsibility |
| --- | --- |
| `platforms/sn34/sn34f28x` | Reset, clocks, timebase, freestanding runtime and chip Flash operations |
| `platforms/sn34/include` | Shared platform interfaces and SDK configuration |
| `tmk_core/protocol/sn34` | SDK USB transport, QMK host driver, report queues and lifecycle hooks |
| `drivers/analog/adc_mux` | ADC/MUX frame production and buffer leasing |
| `drivers/analog/keychron_he` | Sample-to-matrix mapping, travel conversion and Keychron integration |
| `drivers/eeprom/sn34*` | Cached EEPROM and CRC-protected bank commits |
| `drivers/led/ws2812_sn34.c` | SPI/DMA WS2812 output |
| `keyboards/<keyboard>/board` | Physical wiring, sample identities, LEDs, defaults, memory and persistent-format contracts |
| `util/sn34` | Target generation, build import, host tools and packaging |
| `tests/sn34` | Firmware emulation, model and build regressions |

QMK's existing `quantum/main.c` owns the lifecycle. Keychron's HE algorithms
remain in `keyboards/keychron/common/analog_matrix`; the integration fixes are
committed directly to those upstream files. Only the external SONiX HID class
is patched into a build-local copy. The SDK itself is not included in the fork.

## Target contracts

`board.json` separates sampled slots, electrical identities, physical keys,
QMK coordinates and LED indices. Layer defaults and overrides use stable slot
identities, not display names. `scan.phases` supplies ADC channels and scatter
destinations; generated C preserves inline operations in the interrupt path.
Keys can omit LEDs, and a chain can have additional decorative LEDs.

`storage.json` owns the persistent-format contract. Battle68 retains its v36
matrix coordinates, Fn `(0,0)`, bank addresses, HE layout and VIA compatibility
date. These values are not global SN34 defaults. The compatibility fixture
contains controlled test settings, not an executable OEM image.

`sn34_test` is a synthetic target, not a hardware port. It deliberately uses a
3x5 matrix, 16 sampled slots, two phases, 12 switches, five LEDs, two layers and
different EEPROM banks. Its electrical identifiers do not follow Battle68's
numbering convention.

## Validation and remaining extraction

The migration is implemented in stages so each behavioral boundary can be
checked against the preceding image.

- [x] Import the original owned sources into one QMK history.
- [x] Integrate the seven Keychron patches directly into their source files.
- [x] Move production modules into platform, protocol, driver and board directories.
- [x] Select board, curve, storage and output paths by keyboard/keymap target.
- [x] Generate ADC ranks and scatter from each target's wiring.
- [x] Preserve v36 mapping/default/storage contracts with regression fixtures.
- [x] Extract calibration-provider policy from the EEPROM commit engine.
- [x] Select Bootloader entry/packaging independently of the chip platform.
- [x] Configure optional USB functions and RGB hardware backend per target.
- [x] Extract reusable emulator classes and execute the synthetic target.
- [x] Add portable host/packaging entry points and a dependency lock.
- [x] Validate default, minimal and synthetic builds from a fresh checkout.
- [ ] Validate the final image on physical Battle68 hardware.

Offline scan and Boot decision fixtures record results previously obtained by
executing OEM code. They include source hashes and provenance, but no executable
bytes. These tests exercise the new Flash/startup/scanner code and compare its
behavior to that captured contract; they do not rerun the OEM Boot executable.

Physical timing, analog quality, USB-host behavior and reset/OTA still require
hardware validation. A passing emulation run must not be reported as a physical
keyboard test.

See [the validation record](validation.md) for the tested commit and scope.
