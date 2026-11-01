# Building SN34 targets

The maintained entry point is:

```powershell
uv run util/sn34/cli.py build --keyboard battle68 --keymap default
```

The CLI uses `uv.lock` and separate `.build/python/windows` and
`.build/python/linux` environments. Windows forwards compilation to WSL;
Linux uses the same QMK Make backend.
`uv`, QMK CLI and an ARM GNU toolchain must be available. The migration has been
compiled with GCC 13.2.1. Source and build paths currently must not contain spaces.

Supply SONiX SDK 2.1.4, DFP 2.0.4, CMSIS Core and newlib headers externally.
Configure environment variables `SN34_SDK_DIR`, `SN34_DFP_DIR`, `SN34_CMSIS_DIR`,
and `SN34_NEWLIB_INCLUDE`, or create an ignored `.sn34-local.json`:

```json
{
  "sdk_dir": "../dependencies/sn34f28x_sdk_2.1.4/SDK/HAL",
  "dfp_dir": "../dependencies/SONiX.SN34F2_DFP.2.0.4/Device/Include",
  "cmsis_dir": "../dependencies/CMSIS_5",
  "newlib_include": "../dependencies/newlib/include/newlib",
  "toolchain_bin": "../dependencies/gcc/bin",
  "qmk_bin": "../dependencies/qmk-venv/bin"
}
```

Paths are relative to the repository root. CLI options `--sdk-dir`, `--dfp-dir`,
`--cmsis-dir`, `--newlib-include`, `--toolchain-bin`, and `--qmk-bin` override them.
Windows converts configured dependency paths before entering WSL. Neither SDK
sources, toolchains, a second QMK checkout nor original application images are
stored in this repository.

Required QMK submodule headers can be installed with:

```sh
git submodule update --init --depth 1 lib/lufa
```

Every target gets its own `.build/sn34/<keyboard>/<keymap>/` directory containing
generated tables, source/patch hashes, `firmware.elf`, `firmware.bin`,
`application.bin`, and configurator definitions. The application image includes
the target-specific footer. The QMK raw BIN and application image have different
purposes; OEM updater packaging is a separate operation.

Additional build commands:

```sh
uv run util/sn34/cli.py build --keyboard battle68 --keymap minimal
uv run util/sn34/cli.py build --keyboard sn34_test
uv run util/sn34/cli.py test
uv run util/sn34/cli.py test --keymap minimal
uv run util/sn34/cli.py test --keyboard sn34_test
uv run util/sn34/cli.py test --unit-only
uv run util/sn34/cli.py device --keyboard battle68 status
```

`sn34_test` is a synthetic test target. It has no associated physical keyboard.
The final migrated firmware has not yet been flashed as part of this refactor.

Package an application after its required offline tests pass:

```sh
uv run util/sn34/cli.py package --build-dir .build/sn34/battle68/default
uv run util/sn34/cli.py package --build-dir .build/sn34/battle68/default --settings-backup /path/to/application-readback.bin --updater-template /path/to/oem_updater_v118.exe
```

The updater template stays outside the repository and must match the selected
target's recorded hash/resource contract. Settings preservation checks both
bank CRCs and runs new-firmware startup before accepting the cache. Output goes
to the build's `release/` directory. Synthetic targets cannot create releases.
