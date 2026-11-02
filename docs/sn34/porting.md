# Adding an SN34 keyboard

Create an ordinary QMK keyboard directory. `sn34_test` demonstrates different
geometry and feature choices, but is not a verified hardware wiring guide.

Maintain these sources directly:

- `keyboard.json`: identity, USB IDs/version, matrix dimensions, physical layout,
  dynamic keymap layers and RGB LED layout.
- `config.h`: layer roles, hotkeys, serial number, queue capacity, default HE/RGB
  behavior, `board/board_config.h` and the shared HE interface configuration.
- `profiles.c`: default profile modes and a read-only per-key profile table,
  following the stock Keychron keyboards.
- `rules.mk` and `post_rules.mk`: QMK features and HE, EEPROM and LED drivers,
  following the existing SN34 keyboards.
- `board/board_config.h`: scan sizes and persistent memory constants. Define any
  clock/ADC or memory overrides before including `sn34_defaults.h`. Linker memory
  bounds come from these same headers.
- `board/wiring.h`: GPIO initialization, MUX selection, ADC ranks/scatter and
  optional RGB pin operations. Keep interrupt-path operations inline.
- `board/keys.inc`: sample slot, QMK matrix slot and measured calibration
  endpoints. This table is defined once in the HE frame translation unit.
- `board/hall_curve.inc`: normalized magnetic response data with measurement
  provenance. This is a maintained constant table, not a build-time export.
- `board/configurator.json`: optional configurator layer labels.
- `board/updater.json`: optional production updater-template hash/resource
  contract. Do not copy another keyboard's updater identity.
- `keymaps/`: ordinary QMK keymaps.

Run `qmk compile -kb <keyboard> -km default`. No prepare or import command is
needed. Select RGB, XInput and application OTA through the existing Make flags.
The current scanner uses ADC0; the WS2812 driver uses SPI1 and DMA1 channel 0.
Another peripheral topology requires a suitable driver implementation.

The QMK `custom` bootloader implements the retained footer-validity boot scheme;
select `"bootloader": "custom"` in keyboard metadata.
Changing image validation requires updating both the backend and packaging.

Use normal QMK keyboard hooks for indicators, hotkeys and storage housekeeping.
QMK invokes `housekeeping_task_user` separately. The current calibration adapter
uses the fallback endpoints maintained in `board/keys.inc`.

Add independent measured/reference data and a test plan under
`tests/sn34/boards/<keyboard>/fixtures/`. These fixtures never feed the compiler.
Run `uv run tests/sn34/run.py --keyboard <keyboard>` after compilation.
Changes to sample mapping, persistent coordinates or stored formats need an
explicit compatibility decision and regression evidence. Offline emulation
does not establish physical support.
