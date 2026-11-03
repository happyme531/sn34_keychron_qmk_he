# Independent SN34 flashing

The normal path uses `qmk flash`, uv and a SonixFlasherC build containing the
SN34 ISP reconnect, completion and full-image checks. No official updater EXE
is needed. The retained vendor Bootloader stays installed.

## Host setup

Use the [SN34-enabled SonixFlasherC fork](https://github.com/happyme531/SonixFlasherC).
It is an external project, not a submodule or bundled executable. Its SN34
fixes were introduced in `43c6d7432fcca27beeead12bca06b4dbf7a87d15`, the patch
used by the dated Battle68 hardware record. An arbitrary upstream build may
lack these fixes.

On Linux/WSL, with libusb development headers and USB access configured:

```sh
git clone https://github.com/happyme531/SonixFlasherC.git ../SonixFlasherC
make -C ../SonixFlasherC BACKEND=libusb
```

On Windows, use a Windows build with `BACKEND=hidapi` so the keyboard retains
its normal HID driver. Executable paths below are examples; point them at your
own compatible build.

Set these optional variables in the ignored `.sn34-local.mk`:

```make
UV := uv
SN34_FLASHER := /path/to/sonixflasher
```

For WSL compilation with Windows USB access, `UV` must name Windows `uv.exe`,
and `SN34_FLASHER` must be a Windows path. Keep the checkout and output files
on a Windows drive mounted in WSL. For example:

```make
UV := /mnt/c/Users/example/.local/bin/uv.exe
SN34_FLASHER := C:/tools/sonixflasher.exe
```

Connect one matching keyboard when flashing.
BOOM68 wired has a different first-upgrade handoff from OEM V1.10: its ISP
temporarily retains the application's PID and interface 3. Use the
[BOOM68 first-install instructions](../../keyboards/langtu/boom68/wired/readme.md#刷写).
Once QMK is installed, its normal `7210` reconnect and settings-preserving
upgrade path have been verified on that board as well.
The flasher selects the application OTA HID interface by Usage `ff67/61`;
the snapshot uses the separate QMK Raw HID interface `ff60/61`.

## Compile, back up and flash

From Linux/WSL:

```sh
qmk flash -kb battle68 -km default
```

Or, after compiling, run the host tool directly in PowerShell:

```powershell
uv run util/sn34/flash.py .build/battle68_default.elf --flasher C:/tools/sonixflasher.exe
```

Before any reboot request, the tool checks the ELF identity and memory bounds,
captures the entire live EEPROM cache (including unsaved settings), and writes
`settings-backup.bin`, `application.bin` and `manifest.json`. A revision check
on every 22-byte read detects configuration/calibration changes and restarts
the snapshot, up to three attempts. Key activity and calibration do not block
read-only snapshots; cache changes during either are covered by revision checks.
The snapshot includes remaps, macros, HE profiles, calibration, controller and
RGB settings. It contains no executable code and cannot roll firmware back.

The flasher receives a complete **516096-byte (`0x7e000`)** application at
offset **0**, including settings banks and footer `0xaaaa5555`. Do not give it
the smaller executable-only QMK BIN, add `0x2000`, or pass `-j`. The Bootloader
adds its physical offset itself. Its erase command erases the entire application
including settings; premerging the backup is necessary.

SonixFlasherC closes the application handle and reopens ISP `0c45:7210` after
requesting reboot from Battle68 `0c45:8037`. It checks erase/program completion
and checksums, then returns to application mode. The host tool reconnects and
compares the complete live settings cache against the expected restored cache.
`manifest.json` becomes `verified` only after this comparison. A failure keeps
the backup and records `failed-or-unverified`; investigate before retrying.

Output defaults to a new timestamped directory beside the ELF, under
`<target>_flash/`. `--output-dir` selects a new directory explicitly.

## First upgrade from older firmware

Older builds do not support the snapshot command. The default workflow stops
before requesting reboot when backup is unavailable. Supply a known compatible
application readback or settings snapshot explicitly:

```powershell
uv run util/sn34/flash.py .build/battle68_default.elf --flasher C:/tools/sonixflasher.exe --settings-backup C:/backups/application-readback.bin
```

This restores the settings at the backup's date; newer edits are not included.
Launcher JSON does not include per-key calibration and is not a substitute.
`--reset-settings` explicitly chooses defaults instead of preserving settings.
Through QMK, pass either selection with Make variable `SN34_FLASH_ARGS`:

```sh
qmk flash -kb battle68 -km default -e SN34_FLASH_ARGS='--settings-backup .build/my-backup.bin'
```

Add `--prepare-only` to either entry point to create the files without starting
SonixFlasherC or requesting reboot. With an explicit backup or reset selection,
preparation does not open USB at all. Without those selections it only reads
the live snapshot.

## Storage format

Settings preservation requires the selected board's current magic, version,
size and valid CRCs. Battle68 uses v3, BOOM68 wired v4 and `sn34_test` v1.
The firmware accepts only that current format; incompatible banks initialize
defaults. Host packaging rejects incompatible backups before reboot.

No older EEPROM format is converted. If the installed firmware uses another
format, choose `--reset-settings` and reconfigure afterward. Launcher exports
can help restore user settings, but do not include per-key calibration and are
not a complete settings backup. Current-format backups are copied intact,
including their final macro-buffer bytes.

## Bootloader recovery

If the keyboard is already in ISP, automatic Raw HID backup is unavailable.
Prepare an image using the saved settings backup, then call the same flasher
against the ISP IDs directly, without an application reboot request:

```powershell
uv run util/sn34/flash.py .build/battle68_default.elf --settings-backup C:/backups/settings-backup.bin --prepare-only --output-dir .build/recovery
& C:/tools/sonixflasher.exe -v 0c45/7210 -o 0 -f .build/recovery/application.bin
```

This direct command checks the image and ISP checksums, but does not perform
the Python tool's post-reboot settings comparison. Keep the backup. Firmware
compiled with `SN34_OTA_ENABLE=no` requires manual ISP entry for later updates.

Windows HID application-to-ISP handoff, independent flashing, application
reconnect and a second upgrade with automatic backup and full-cache comparison
were validated on the Battle68 firmware identified in
[the hardware record](standalone-flash-hardware.json). Later source cleanups
have not been flashed as part of the current offline checks. See
[validation scope](validation.md) for remaining physical checks.

This retained SN34 ISP returns checksums in erase/program completion ACKs, but
does not publish a response to standalone command `0x06`. The accompanying
SonixFlasherC checks the completion ACK/checksum without sending that query.
Older flasher builds may stall USB control transfers after issuing it; unplug
and reconnect the keyboard once, then use the corrected flasher against ISP
`0c45:7210` to recover with the prepared complete application image.
