# /// script
# dependencies = ["pyelftools"]
# ///
"""Build BAT68 through QMK Make (Windows uses WSL); no parallel source list."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import subprocess
from bat68_build_config import BuildPaths, ROOT, write_if_changed


def linux_path(path, distro):
    return subprocess.check_output(["wsl.exe", "-d", distro, "--exec", "wslpath", "-a", path.as_posix()],
                                   text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="Generate inputs without compiling")
    parser.add_argument("--import-only", action="store_true", help="Import a completed direct QMK build")
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--qmk-dir", type=Path)
    parser.add_argument("--sdk-dir", type=Path, help="SONiX SDK HAL directory")
    parser.add_argument("--dfp-dir", type=Path, help="SONiX device header directory")
    parser.add_argument("--cmsis-dir", type=Path)
    parser.add_argument("--newlib-include", type=Path)
    parser.add_argument("--keymap", default="default")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--wsl-distro", default=os.environ.get("BAT68_WSL_DISTRO", "Ubuntu"))
    args = parser.parse_args()
    if args.prepare_only and args.import_only:
        parser.error("--prepare-only and --import-only are mutually exclusive")
    if args.jobs < 1 or not re.fullmatch(r"[A-Za-z0-9_]+", args.keymap):
        parser.error("jobs must be positive and keymap must be a QMK keymap directory name")
    overrides = {field: (ROOT / value).resolve() for field, value in
                 (("build", args.build_dir), ("qmk", args.qmk_dir), ("sdk", args.sdk_dir),
                  ("dfp", args.dfp_dir), ("cmsis", args.cmsis_dir), ("newlib", args.newlib_include)) if value is not None}
    paths = replace(BuildPaths.environment(), **overrides)
    paths.validate()
    os.environ.update(paths.export())
    os.environ["BAT68_ROOT"] = str(ROOT)
    if os.name == "nt" and not args.import_only:
        command = ["wsl.exe", "-d", args.wsl_distro, "--exec", "bash",
                   linux_path(ROOT / "tools/build_bat68_qmk.sh", args.wsl_distro)]
        for option, path in (("build-dir", paths.build), ("qmk-dir", paths.qmk), ("sdk-dir", paths.sdk),
                             ("dfp-dir", paths.dfp), ("cmsis-dir", paths.cmsis), ("newlib-include", paths.newlib)):
            command += ["--" + option, linux_path(path, args.wsl_distro)]
        command += ["--keymap", args.keymap, "--jobs", str(args.jobs)]
        if args.prepare_only:
            command.append("--prepare-only")
        subprocess.run(command, check=True)
        return
    if not args.import_only:
        from bat68_model import sync_keyboard_definition
        sync_keyboard_definition(paths.qmk)
    if args.prepare_only:
        from prepare_bat68 import prepare
        prepare(paths)
        return
    if not args.import_only:
        paths.build.mkdir(parents=True, exist_ok=True)
        write_if_changed(paths.build / "manifest.json", json.dumps({"status": "BUILDING_NOT_FLASHED"}) + "\n")
        # External sources contain ../ components. QMK's object paths can
        # otherwise escape obj_<keymap> and collide across keymaps/builds.
        qmk_build=os.path.relpath(paths.build/"qmk",paths.qmk).replace("\\","/")
        subprocess.run(["qmk", "compile", "-kb", "battle68", "-km", args.keymap, "-j", str(args.jobs),
                        "-e", "BUILD_DIR="+qmk_build],
                       cwd=paths.qmk, check=True)
    from import_qmk_build import import_build
    import_build(paths, keymap=args.keymap)


if __name__ == "__main__":
    main()
