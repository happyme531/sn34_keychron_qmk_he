BAT68 production board contracts

bat68.json is the maintained source for physical key identity, electrical/raw
mapping, persistent QMK matrix coordinates, initial Hall endpoints, LED order,
USB identity and layer roles. Display names do not determine matrix positions.
In particular, physical raw slot 90 remains Fn at QMK (0,0).

storage.json owns application/RAM bounds, Flash pages, EEPROM banks, header
format/version, HE offsets and VIA's persistent compatibility date. Firmware
headers, linker symbols and host packaging tools consume this same contract.
VIA's compatibility date is deliberately independent of QMK_BUILDDATE: changing
the actual build time must not reset stored keymaps or macros.

hall_curve.json contains the existing derived numeric response curve. Released
references and estimated bottoms retain their previous meaning; none of these
values are a physical millimetre calibration. Historical evidence remains in
analysis/, but production table generation does not load its board snapshots.

Run tools/build_bat68.py to generate board/storage headers and synchronize the
owned keyboards/battle68/keyboard.json and config.h metadata. The config.h
dimensions are literal because QMK's metadata parser does not follow includes.
Do not edit generated metadata directly. Layout digests and tests/fixtures/
bat68_v36_compatibility.json freeze the installed format; deliberate changes
need a reviewed settings migration, including the stored VIA and HE regions.

Keyboard-level process_record_kb lives in firmware/qmk/battle68.c. The default
keymap contains only its mapping and optional Tap Dance/Combo examples. The
minimal keymap disables those examples and tests independent board/user hooks.

QMK matrix_common.c owns the public matrix API and callbacks. The board uses
CUSTOM_MATRIX=lite and selects upstream debounce/none.c explicitly because HE
already determines trigger state. The pinned QMK metadata schema requires the
"custom" debounce selector for this otherwise standard implementation.

Keychron's common Raw HID dispatcher owns Launcher identity, capabilities,
matrix queries and command routing. The board adapter only translates RGB IDs,
validates HE/NKRO writes and uses the upstream handler extension hooks. Feature
flags omit the unavailable DFU-info, language and Quick Start commands.
