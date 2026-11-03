# SN34 validation

## Reproduce the checks

Build the selected target first; offline tests consume its standard ELF:

```sh
qmk compile -kb battle68 -km default
qmk compile -kb langtu/boom68/wired -km default
qmk compile -kb sn34_test -km default
uv run tests/sn34/run.py --keyboard battle68
uv run tests/sn34/run.py --keyboard langtu/boom68/wired
uv run tests/sn34/run.py --keyboard sn34_test
```

Use `--elf <path>` for a custom build directory and `--layout <name>` for a
keyboard with several layouts. Logs and JSON results are written to
`.build/sn34-tests/<target>/`. Linker contract probes run when
`arm-none-eabi-gcc` is on PATH; run them in the ARM build environment if the
host-only test run skips them.

| Area | Coverage |
| --- | --- |
| Build integration | Target-local SDK objects, ELF/BIN agreement, packaging, selected RGB features and configurator output |
| QMK/HE | Key events, profile writes and selection, calibration, advanced actions and user hook ordering |
| USB | Descriptors at both speeds, suspend/reconnect, queues, report ordering and recovery |
| Storage | Current-format bank acceptance, CRC/header checks, save/reload, snapshots and settings-preserving packaging |
| Flash | Production HAL execution with modeled controller effects, interrupted writes, code/footer boundaries |
| Board drivers | Battle68 scan/boot references; BOOM68 bank settling, encoder/button and RGB output; synthetic geometry |

These tests execute ARM firmware in Unicorn with modeled peripherals. They do
not measure physical latency, analog settling, electrical noise, Flash endurance
or USB-host compatibility. An incompatible EEPROM version is rejected rather
than converted; old payloads are not migration fixtures.

The 2026-11-03 current-format cleanup was checked with builds and offline suites
for all three targets, plus ARM linker contract probes. Current EEPROM memory
bounds, versions, key/calibration tables, default profiles and HID report
definitions matched the preceding build. The removed conversion hooks and
legacy-version linker export were absent from the new ELFs. This run did not
flash a keyboard.

## Dated hardware evidence

The following records apply to their recorded firmware, not automatically to
every later commit. Local `.build/` evidence paths inside them identify the
original workstation artifacts and are not distributed dependencies.

| Date | Keyboard | Evidence |
| --- | --- | --- |
| 2026-11-01 | Battle68 | [Initial OEM-updater installation](cleanup-installation.json), USB enumeration and public-settings comparison |
| 2026-11-03 | Battle68 | [Independent flashing and automatic upgrade](standalone-flash-hardware.json), including full-cache comparison |
| 2026-11-03 | Battle68 | [Launcher HE import fix](launcher-import-validation.json), settings preservation and user confirmation |
| 2026-11-03 | BOOM68 wired | [Board validation](boom68-validation.json), settling measurements, settings/encoder checks and user confirmation |

Whole-board scan-rate measurements, cold-start/power-loss acceptance and
long-running USB/typing checks remain separate hardware work. BOOM68's exact
light-box geometry and physical travel scale are also not established by the
offline model. See the [Battle68](../../keyboards/battle68/readme.md) and
[BOOM68](../../keyboards/langtu/boom68/wired/readme.md) notes.

Superseded refactor reports and commands for removed build tools have been
removed from the active documentation. Their original snapshots remain in Git
history; current commands are maintained in [build.md](build.md).
