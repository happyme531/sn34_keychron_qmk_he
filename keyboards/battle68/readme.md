# Battle68

QMK target: `battle68`, SONiX SN34F280, USB `0C45:8037`.
The port scans 67 Hall switches into a 6x16 logical matrix, with the physical
Fn key at `(0,0)`. RGB and the Caps Lock, Win Lock and macOS status LEDs are
handled by separate board hooks.

## Build and configure

Configure external dependencies as described in the
[SN34 build instructions](../../docs/sn34/build.md), then run:

```sh
qmk compile -kb battle68 -km default
uv run tests/sn34/run.py --keyboard battle68
uv run util/sn34/export.py .build/battle68_default.elf
```

The `minimal` keymap exercises ordinary board/user hooks without the default
tap-dance and combo definitions:

```sh
qmk compile -kb battle68 -km minimal
uv run tests/sn34/run.py --keyboard battle68 --keymap minimal
```

Import the exported `sn34_via.json` or `sn34_launcher.json` from
`.build/battle68_default_config/`. Layer labels are maintained in
`board/configurator.json`; the four layers are Windows base/Fn and macOS
base/Fn. The three HE profiles default to regular, rapid trigger and regular.

## Default controls

| Chord | Action |
| --- | --- |
| Fn + 1 through 0, minus, equals | F1 through F12 |
| Fn + Esc | Grave accent |
| Fn + Backspace | Delete |
| Fn + W/A/S/D | Arrow keys |
| Fn + P + Z/X/C | HE profile 1/2/3 |

Win Lock (`QK_KB_30`) and Windows/macOS selection (`QK_KB_31`) can be assigned
through a keymap or configurator. They are not bound in the default keymap.
The default keymap also provides a tap-dance action (Esc/Caps Lock) and an
F23+F24 Caps Lock combo that can be assigned through VIA.

## Flashing and storage

Follow [flashing and recovery](../../docs/sn34/flashing.md). Set
`SN34_FLASHER` to a compatible external SonixFlasherC executable. When compatible
QMK firmware is already running, `qmk flash -kb battle68 -km default` backs up
settings before flashing and verifies them after reboot.

The complete application is `0x7e000` bytes at User-ROM offset zero, including
the retained bootloader footer. Do not directly flash the smaller QMK BIN.
The current EEPROM format is v3. Older formats are rejected; use
`--reset-settings` for an incompatible installation and reconfigure afterward.
Current-format settings, calibration, macros and profiles can be preserved
across upgrades. Settings are committed after five seconds without key activity.

## Wiring and validation

Maintained wiring, ADC ranks, sample mapping and calibration references live
under `board/`. The scanner uses ADC0 with eight binary-MUX phases and 96
sample slots. The response curve and fallback endpoints have independent
reference data under `tests/sn34/boards/battle68/fixtures/`.

Offline tests cover typing, profiles, USB lifecycle/backpressure, scanner and
boot references, calibration, persistence and interrupted Flash writes.
Dated hardware records cover independent flashing, settings preservation and
Launcher HE imports. See [validation scope](../../docs/sn34/validation.md) for
the distinction between those records and the latest source changes.
