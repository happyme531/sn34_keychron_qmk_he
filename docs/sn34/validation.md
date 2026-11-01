# Refactor validation

Tested code commit: `38ba288d321ec1d5c6c7abfbcee03d47acd16215`.
The tests were run from an independent, clean Git checkout with no preceding
build directory. SDK, DFP, CMSIS and toolchain locations were supplied as ignored
local configuration. No source overlay or second QMK tree was used.

| Target | Code bytes | Offline validation | Compile objects | Recorded inputs |
| --- | ---: | --- | ---: | ---: |
| Battle68 default | 85,704 | All eight firmware groups | 113 | 577 |
| Battle68 minimal | 82,408 | Independent board/user hooks | 111 | 569 |
| Synthetic SN34 target | 56,008 | Key input, persistence and omitted interfaces | 100 | 485 |

Twenty host/model/build contract tests also passed. The three builds have no
shared object files, and every object is within its own keyboard/keymap build
directory. Owned source inputs resolve inside that checkout; external inputs
are restricted to the explicitly configured dependency roots. Keychron HE/VIA
compile directly from their tracked, patched source files.

The synthetic target exercises a 3x5 matrix, 16 sample slots, two scan phases,
12 switches, five independently described LEDs and different EEPROM banks.
RGB, XInput, diagnostics and application OTA interfaces are disabled; the
remaining three USB interfaces and Raw HID routing were executed in emulation.

The default regression includes the frozen v36 keymap, calibration defaults,
LED mapping and persistent-format contracts, USB/backpressure and lifecycle
behavior, startup, ADC scatter/mux reference results, and interrupted Flash
commits. OEM scan/Boot references are captured data, not bundled executables.

Packaging was tested with the controlled v36 settings fixture and an external
OEM updater template. New-firmware startup preserved the complete expected
cache, the application resource matched the packaged image, and the firmware
word checksum and PE checksum were verified. No updater template is stored in
the repository.

Default code SHA-256:
`9ace99877f457c9589ab2ec06df26a5a3adb74f83578d723dcbfa7b7b846fe5f`.

These are offline results. Physical cold boot, key feel/noise, USB hosts,
lighting waveforms, power loss and real OTA require a separate hardware run.
