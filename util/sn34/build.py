# /// script
# dependencies = ["pyelftools"]
# ///
"""Build any configured SN34 QMK target with external SDK/toolchain dependencies."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from build_config import BuildPaths, ROOT, local_config, write_if_changed


def linux_path(path, distro):
    return subprocess.check_output(["wsl.exe", "-d", distro, "--exec", "wslpath", "-a", path.as_posix()], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyboard", default=os.environ.get("SN34_KEYBOARD", "battle68"))
    parser.add_argument("--keymap", default="default")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    for name in ("build-dir", "sdk-dir", "dfp-dir", "cmsis-dir", "newlib-include", "toolchain-bin", "qmk-bin"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--wsl-distro", default=os.environ.get("SN34_WSL_DISTRO", "Ubuntu"))
    args = parser.parse_args()
    if args.prepare_only and args.import_only:
        parser.error("--prepare-only and --import-only are mutually exclusive")
    if args.jobs < 1 or not re.fullmatch(r"[A-Za-z0-9_]+", args.keymap):
        parser.error("jobs must be positive and keymap must be a QMK keymap directory name")
    os.environ.update(SN34_KEYBOARD=args.keyboard, SN34_KEYMAP=args.keymap)
    for name in ("build_dir", "sdk_dir", "dfp_dir", "cmsis_dir", "newlib_include", "toolchain_bin", "qmk_bin"):
        value = getattr(args, name)
        if value is not None:
            os.environ["SN34_" + name.upper()] = str((ROOT / value).resolve())
    paths = BuildPaths.environment()
    paths.validate()
    if os.name == "nt" and not args.import_only:
        command = ["wsl.exe", "-d", args.wsl_distro, "--exec", "bash",
                   linux_path(ROOT / "util/sn34/build.sh", args.wsl_distro)]
        for option, path in (("build-dir", paths.build), ("sdk-dir", paths.sdk), ("dfp-dir", paths.dfp),
                             ("cmsis-dir", paths.cmsis), ("newlib-include", paths.newlib)):
            command += ["--" + option, linux_path(path, args.wsl_distro)]
        for option in ("toolchain_bin", "qmk_bin"):
            value = os.environ.get("SN34_" + option.upper()) or local_config().get(option)
            if value:
                command += ["--" + option.replace("_", "-"), linux_path((ROOT / value).resolve(), args.wsl_distro)]
        command += ["--keyboard", args.keyboard, "--keymap", args.keymap, "--jobs", str(args.jobs)]
        if args.prepare_only: command.append("--prepare-only")
        subprocess.run(command, check=True)
        return
    for option in ("toolchain_bin", "qmk_bin"):
        value = os.environ.get("SN34_" + option.upper()) or local_config().get(option)
        if value:
            os.environ["PATH"] = str((ROOT / value).resolve()) + os.pathsep + os.environ["PATH"]
    os.environ.update(paths.export())
    if not args.import_only:
        from model import sync_keyboard_definition
        sync_keyboard_definition()
    if args.prepare_only:
        from prepare import prepare
        prepare(paths)
        return
    if not args.import_only:
        paths.build.mkdir(parents=True, exist_ok=True)
        write_if_changed(paths.build / "manifest.json", json.dumps({"status": "BUILDING_NOT_FLASHED"}) + "\n")
        qmk_build = os.path.relpath(paths.build / "qmk", ROOT).replace("\\", "/")
        subprocess.run(["qmk", "compile", "-kb", args.keyboard, "-km", args.keymap, "-j", str(args.jobs),
                        "-e", "BUILD_DIR=" + qmk_build], cwd=ROOT, check=True)
    from import_build import import_build
    import_build(paths, keymap=args.keymap)


if __name__ == "__main__":
    main()

