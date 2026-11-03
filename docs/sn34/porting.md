# Adding an SN34 keyboard

Create an ordinary QMK keyboard directory. `sn34_test` demonstrates different
geometry and feature choices, but is not a verified hardware wiring guide.

Maintain these sources directly:

- `keyboard.json`: identity, USB IDs/version, matrix dimensions, physical layout,
  dynamic keymap layers, RGB LED layout and `rgb_matrix.animations`.
- `config.h`: layer roles, hotkeys, serial number, queue capacity, default HE/RGB
  behavior, `board_config.h` and the shared HE interface configuration. Use the
  bare header name so a variant can override it through the board include path.
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
  endpoints. This table is defined once in the matrix adapter translation unit.
- `board/hall_curve.inc`: normalized magnetic response data with measurement
  provenance. This is a maintained constant table, not a build-time export.
- `board/configurator.json`: optional configurator layer labels.
- `board/updater.json`: optional production updater-template hash/resource
  contract. Do not copy another keyboard's updater identity.
- `keymaps/`: ordinary QMK keymaps.

Parent `info.json`, rules, config headers and individual `board/` files can be
inherited using QMK's keyboard hierarchy. The linker uses the same board header
search order as C. Optional host tools merge maintained JSON metadata and find
configurator/updater resources through that hierarchy as well.

Run `qmk compile -kb <keyboard> -km default`. No prepare or import command is
needed. Select RGB, XInput and application OTA through the existing Make flags.
The current scanner uses ADC0; the WS2812 driver uses SPI1 and DMA1 channel 0.
Another peripheral topology requires a suitable driver implementation.
The Launcher adapter requires VIA and Raw HID; NKRO, mouse keys, extra keys and
joystick remain optional. The hot HE scan and shared core use LTO in just those
two translation units, without enabling LTO across the SDK or all of QMK.

The QMK `custom` bootloader implements the retained footer-validity boot scheme;
select `"bootloader": "custom"` in keyboard metadata.
Changing image validation requires updating both the backend and packaging.
This retained bootloader requires application offset zero; nonzero
`SN34_APP_ORIGIN` is rejected.

Use normal QMK keyboard hooks for indicators, hotkeys and storage housekeeping.
For mixed Hall/digital boards, define `SN34_MATRIX_EXTRA_ENABLE` and implement
`sn34_matrix_scan_extra()` to merge
debounced digital keys into the raw matrix. It runs even without a fresh ADC
frame; the Hall mask and calibration table must contain Hall switches only.
BOOM68 demonstrates active-low bank enables, an encoder button and extra RGB
pixels: see [its board documentation](../../keyboards/langtu/boom68/wired/readme.md).
QMK invokes `housekeeping_task_user` separately. The current calibration adapter
uses the fallback endpoints maintained in `board/keys.inc`.
New boards accept their current EEPROM version only. Declare any supported
old versions in `SN34_EEPROM_LEGACY_VERSIONS` (bit N accepts version N), and
implement `sn34_eeprom_migrate()` if their payload needs conversion before
QMK/HE initialization. Battle68's historical v1/v2 handling is board-owned.

Add independent measured/reference data and a test plan under
`tests/sn34/boards/<keyboard>/fixtures/`. These fixtures never feed the compiler.
Run `uv run tests/sn34/run.py --keyboard <keyboard>` after compilation.
Changes to sample mapping, persistent coordinates or stored formats need an
explicit compatibility decision and regression evidence. Offline emulation
does not establish physical support.
