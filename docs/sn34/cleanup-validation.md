# Diagnostic removal and cleanup validation

The custom diagnostic HID interface, command dispatcher, host probe tools,
profiling counters, retained mailbox and experimental scan modes were removed.
The stack now starts at the end of RAM; the mailbox's former 64-byte reservation
and its duplicated stack-address setting were removed as well.
QMK/Keychron Raw HID, application OTA and automatic EEPROM persistence remain.
Battle68 exposes five USB interfaces: Boot keyboard, shared HID, OTA Feature,
Raw HID and XInput. The synthetic target exposes three interfaces.

The keyboard's USB device version has one source in `board.json`. Generated
mapping and calibration use one shared table, QMK features are selected in Make,
and each target owns a single script/result test plan. Compatibility checks
freeze generated table values independently of C type names and formatting.
The semantic hashes were extracted from the preceding verified build after
checking its original v36 table hashes; the persistent v36 bank fixture is unchanged.

All 22 host/model/build tests passed, followed by eight Battle68 default
firmware groups, the minimal board/user-hook group and the synthetic target
group. Every target's input hashes and test image hashes were verified.

| Target | Previous code bytes | Current code bytes | Removed bytes |
| --- | ---: | ---: | ---: |
| Battle68 default | 85,704 | 81,680 | 4,024 |
| Battle68 minimal | 82,408 | 78,376 | 4,032 |
| Synthetic SN34 | 56,008 | 54,528 | 1,480 |

The default ELF contains one 536-byte board table instead of two 402-byte
mapping tables plus a separate 536-byte calibration table. Removing the unused
queue interface member also saves 256 bytes of RAM with the default capacity.
The actual OTA Feature request was executed in emulation on its renumbered
interface, and real PCD FIFO allocation leaves two of eight FIFOs available.
The scanner checks include generation-counter overflow and leased-frame stability.

Settings-preserving packaging passed with the controlled v36 fixture and the
external OEM updater template. New-firmware startup preserved the expected
cache, and resource contents, firmware checksum and PE checksum were checked.
Exact image hashes and final offline results are recorded in
[cleanup-validation.json](cleanup-validation.json).
This work uses the current worktree with external SDK/toolchain dependencies.
No physical keyboard was flashed during the offline validation above.

On 2026-11-01, the user subsequently authorized installation on the connected
Battle68. The existing application, Bootloader and public settings were backed
up, and the OEM updater reported success at 100%. The installed build identifies
itself as `v2.0.0 2026-11-01-22:54:56`. Windows enumerated interfaces 0 through 4,
including the XInput driver; Raw HID and OTA moved to interfaces 3 and 2.
The custom diagnostic interface is absent. Public keymaps, macros, HE profiles,
controller settings and RGB settings matched the pre-install snapshot.
See [the installation record](cleanup-installation.json).

Physical typing and key feel await the user's test. Cold power-on, analog
quality, new-firmware OTA re-entry and power interruption remain separate checks.
