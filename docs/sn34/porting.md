# Adding an SN34 keyboard

Create an ordinary QMK keyboard directory. `sn34_test` demonstrates different
geometry and feature choices, but is not a verified hardware wiring guide.

Maintain these sources directly:

- `keyboard.json`: identity, USB IDs/version, matrix dimensions, physical layout,
  dynamic keymap layers, RGB LED layout and `rgb_matrix.animations`.
- `config.h`: layer roles, hotkeys, serial number, queue capacity, default HE/RGB
  behavior, `board_config.h` and the shared HE interface configuration. Use the
  bare header name so a variant can override it through the board include path.
  Use `1`/`0` for boolean settings read by this checkout's QMK metadata parser,
  including `RGB_MATRIX_DEFAULT_ON`; the C spelling `true` is not recognized there.
  The USB report queue defaults to 256 slots with 96 reserved for input bursts;
  override it only when the board needs a different capacity.
- `profiles.c`: default profile modes and a read-only per-key profile table,
  following the stock Keychron keyboards.
- `rules.mk`: product features, driver selectors and board sources, followed by
  `include drivers/analog/sn34.mk` for HE, cached EEPROM and no-debounce support.
  The adapter supplies shared sources and selective LTO settings. Keep driver
  selectors and joystick dimensions explicit for QMK's metadata reader.
- `post_rules.mk`: board Bootmagic policy and `include drivers/led/sn34.mk`,
  after QMK has finalized feature selection.
- `board/board_config.h`: scan sizes and persistent memory constants. Define any
  clock/ADC or memory overrides before including `sn34_defaults.h`. Linker memory
  bounds come from these same headers.
- `board/wiring.h`: GPIO initialization, MUX selection, ADC ranks/scatter and
  optional RGB pin operations. Keep interrupt-path operations inline.
- `board/keys.inc`: sample slot, QMK matrix slot and measured calibration
  endpoints. This table is defined once in the matrix adapter translation unit.
- `board/hall_curve.inc`: normalized magnetic response data with measurement
  provenance. This is a maintained constant table, not a build-time export.
- `board/configurator.json`: layer labels and optional encoder metadata,
  required by the configurator export tool; not needed for compilation.
- `board/updater.json`: optional production updater-template hash/resource
  contract. Do not copy another keyboard's updater identity.
- `keymaps/`: ordinary QMK keymaps.

Parent `info.json`, rules, config headers and individual `board/` files can be
inherited using QMK's keyboard hierarchy. The linker uses the same board header
search order as C. Optional host tools merge maintained JSON metadata and find
configurator/updater resources through that hierarchy as well. Offline tests use
the same metadata reader, while measured wiring and storage fixtures stay independent.

The Keychron HE wire protocol supports at most eight matrix rows and 24 columns
with the current 32-byte Raw HID packets. The shared HE core rejects larger
matrices at compile time; host tools size per-key masks from the selected matrix.

Run `qmk compile -kb <keyboard> -km default`. No prepare or import command is
needed. Select RGB, XInput and application OTA through the existing Make flags.
The current scanner uses ADC0; the WS2812 driver uses SPI1 and DMA1 channel 0.
Another peripheral topology requires a suitable driver implementation.
The Launcher adapter requires VIA, which enables Raw HID automatically.
NKRO, mouse keys, extra keys and joystick remain optional.
The hot HE scan and shared core use LTO in just those
two translation units, without enabling LTO across the SDK or all of QMK.

The QMK `custom` bootloader implements the retained footer-validity boot scheme;
select `"bootloader": "custom"` in keyboard metadata.
Changing image validation requires updating both the backend and packaging.
This retained bootloader requires application offset zero; nonzero
`SN34_APP_ORIGIN` is rejected.
The linker also rejects overlapping or unaligned EEPROM banks, banks outside
the reserved settings area, invalid payload/header sizes and a misplaced footer.
Default code/end bounds are derived from both banks, regardless of their order.

Use normal QMK keyboard hooks for indicators, hotkeys and storage housekeeping.
Call `sn34_he_task()` from `housekeeping_task_kb()` and keep board-specific
indicator/policy work in that hook. In key/RGB hooks, call the corresponding user
hook once and respect `false` before invoking `process_record_profile()` or
`analog_matrix_indicator()`. If the board consumes a chord's press, clear its
release bookkeeping even when the user vetoes release; keep that release out of
QMK's ordinary key processing.
For mixed Hall/digital boards, define `SN34_MATRIX_EXTRA_ENABLE` and implement
`sn34_matrix_scan_extra()` to merge
debounced digital keys into the raw matrix. It runs even without a fresh ADC
frame; the Hall mask and calibration table must contain Hall switches only.
BOOM68 demonstrates active-low bank enables, an encoder button and extra RGB
pixels: see [its board documentation](../../keyboards/langtu/boom68/wired/readme.md).

For Keychron Per-key RGB and Mix RGB, set `KEYCHRON_RGB_ENABLE = yes` in
`rules.mk` and reserve `SN34_CUSTOM_RGB_STORAGE_SIZE` in `board_config.h`.
The reservation must fit `6 + 4 * RGB_MATRIX_LED_COUNT +
8 * EFFECT_LAYERS * EFFECTS_PER_LAYER` bytes plus a four-byte initialization
version; round up as appropriate (BOOM68 uses 512). The reservation also applies
to builds without RGB so VIA addresses remain stable. Adding it changes the
storage layout and requires a new EEPROM version and VIA compatibility date.
Optionally define `SN34_RGB_ZONE2_START` to place that LED and all later LEDs
in zone 2 by default; otherwise all LEDs start in zone 1. The adapter owns RGB
initialization in `keyboard_post_init_kb`; boards enabling it should keep their
post-init work in `keyboard_post_init_user`, or arrange a shared hook before
overriding it. Call `process_record_keychron_rgb()` after the user hook in
`process_record_kb` to apply the upstream custom-mode shortcut behavior.

QMK invokes `housekeeping_task_user` separately. The current calibration adapter
uses the fallback endpoints maintained in `board/keys.inc`.
Each board accepts only its current EEPROM version. Choose a unique magic and
define `SN34_EEPROM_VERSION`; a new board may start at v1. Invalid versions
initialize defaults in firmware and are rejected by host packaging. There are
no migration callbacks or legacy-version declarations. Change the version
when the stored layout changes and document that reconfiguration is required.

Add independent measured/reference data and a test plan under
`tests/sn34/boards/<keyboard>/fixtures/`. These fixtures never feed the compiler.
`storage.json` declares the current `eeprom_version` independently of the build
headers; host and firmware tests reject every other version.
Run `uv run tests/sn34/run.py --keyboard <keyboard>` after compilation.
Layouts may use normal QMK names such as `LAYOUT_ansi_68`. If more than one
layout is defined, select one with `--layout <name>` in host tools and tests.
Changes to sample mapping, persistent coordinates or stored formats need an
explicit compatibility decision and regression evidence. Offline emulation
does not establish physical support.
