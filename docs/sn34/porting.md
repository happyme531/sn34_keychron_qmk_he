# Adding a keyboard

Start with a new `keyboards/<name>/` directory. `sn34_test` demonstrates geometry
and feature differences; it is a synthetic fixture, not a verified wiring guide.
Use measured wiring and calibration provenance for a real keyboard.

Each target owns:

- `keyboard.json` and `config.h`: generated QMK metadata, checked into Git so
  QMK can discover the target before platform preparation.
- `rules.mk`: ordinary QMK features, MCU and custom-matrix selection.
- `config_base.h`: entry into the shared HE configuration and board overrides.
- `board/target.json`: Bootloader backend, protocol/RGB feature selection,
  validation profiles and optional external updater-template contract.
- `board/board.json`: keys, stable sample identities, QMK coordinates, layers,
  ADC phases, GPIO/clock settings and independent LED mapping.
- `board/storage.json`: memory partitions, EEPROM identity/version, HE offsets
  and the VIA compatibility date.
- `board/hall_curve.json`: numerical response curve and its provenance.
- `keymaps/`: default and optional user keymaps.

Run `uv run util/sn34/cli.py build --keyboard <name> --prepare-only` after editing
the model. Check the generated QMK metadata diff, then build and test the target.
Use a separate EEPROM identity for a new board; do not copy Battle68's v36
persistence identity or its Fn-coordinate exception into unrelated hardware.

## Existing backends

The chip platform currently supports SN34F280. The ADC0/MUX backend accepts
per-phase channel-to-slot mappings, channel rank order, pre-samples, phase pins,
gate wiring and analog-front-end GPIO operations. Its three-buffer frame API
is independent of the number of phases, sampled slots or logical matrix shape.
Another scanner implementation should implement that same acquire/release API
and be registered in `util/sn34/prepare.py`.

The current RGB backend uses SPI1 and DMA1 channel 0. Pins, the enable GPIO and
SPI divisor come from the board model. A different peripheral/channel topology
needs a corresponding backend. RGB, XInput, diagnostics and application OTA
interfaces can be omitted independently. `target.json`'s RGB selection must
agree with QMK's `RGB_MATRIX_ENABLE` in `rules.mk`; builds reject disagreement.

The `vendor_footer` Bootloader backend implements the retained footer-validity
scheme used by Battle68. Selecting the same MCU does not select this backend
automatically: every target names its Bootloader policy explicitly. Add a new
backend for different entry, partition or image-validation behavior.

## Board services

Indicator hooks have empty weak defaults and can be implemented by the board.
Keyboard behavior remains in the normal QMK board/user hooks. Shared modules
must not depend on a specific keymap.

`sn34_board_calibration_read(buffer, size)` can provide a validated factory
calibration record, for example from a board EEPROM. Returning false selects
the generated per-key fallback endpoints. This Keychron interface is separate
from the Flash bank engine and from runtime calibration stored in the cache.

Changing sample IDs, logical coordinates or persisted formats needs an explicit
migration and fixtures for that board. Shared tests cover model validation,
build isolation, host-device selection and actual ARM execution. Add board
regressions before claiming physical support.
