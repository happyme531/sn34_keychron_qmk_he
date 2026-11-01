"""Locations and provenance shared by preparation, QMK Make and packaging."""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = json.loads((ROOT / "firmware/qmk/upstream.json").read_text(encoding="utf-8"))


def location(name, default):
    return (ROOT / os.environ.get(name, default)).resolve()


@dataclass(frozen=True)
class BuildPaths:
    build: Path
    qmk: Path
    sdk: Path
    dfp: Path
    cmsis: Path
    newlib: Path

    @classmethod
    def environment(cls):
        return cls(
            location("BAT68_BUILD_DIR", "build/bat68"),
            location("BAT68_QMK_DIR", "keychron_qmk"),
            location("BAT68_SDK_DIR", "analysis/sdk/sn34f28x_sdk_2.1.4/SDK/HAL"),
            location("BAT68_DFP_DIR", "analysis/sdk/SONiX.SN34F2_DFP.2.0.4/Device/Include"),
            location("BAT68_CMSIS_DIR", "reference/CMSIS_5"),
            location("BAT68_NEWLIB_INCLUDE", "toolchains/newlib/extracted/usr/include/newlib"),
        )

    def export(self):
        names = ("BUILD_DIR", "QMK_DIR", "SDK_DIR", "DFP_DIR", "CMSIS_DIR", "NEWLIB_INCLUDE")
        return {"BAT68_" + name: str(value) for name, value in zip(names, self.__dict__.values())}

    def roots(self):
        return {"workspace": ROOT, "qmk": self.qmk, "sdk": self.sdk,
                "dfp": self.dfp, "cmsis": self.cmsis, "newlib": self.newlib}

    def validate(self):
        for folder in (ROOT, *self.__dict__.values()):
            if any(c.isspace() for c in str(folder)):
                raise ValueError(f"QMK Make requires source/build paths without whitespace: {folder}")
        for name, path in self.roots().items():
            if not path.is_dir():
                raise FileNotFoundError(f"Missing {name} dependency: {path}; configure its BAT68 path override")
        if self.build == ROOT or self.build in ROOT.parents:
            raise ValueError("The build directory must not be the workspace or its parent")

    def label(self, path):
        path = path.resolve()
        if path.is_relative_to(ROOT):
            return path.relative_to(ROOT).as_posix()
        for name, root in self.roots().items():
            if path.is_relative_to(root):
                return f"@{name}/" + path.relative_to(root).as_posix()
        if path.is_relative_to(self.build):
            return "@build/" + path.relative_to(self.build).as_posix()
        raise ValueError(f"Build input is outside the configured dependency roots: {path}")

    def serialized_roots(self):
        roots = {**self.roots(), "build": self.build}
        return {name: (path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path))
                for name, path in roots.items()}


def write_if_changed(path, data):
    path = Path(path)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def qmk_revision(qmk):
    def git(*args):
        return subprocess.run(["git", "-C", str(qmk), *args], text=True, capture_output=True, check=True).stdout.strip()
    head = git("rev-parse", "HEAD")
    compatible = subprocess.run(["git", "-C", str(qmk), "merge-base", "--is-ancestor",
                                 UPSTREAM["base_commit"], head], capture_output=True)
    if compatible.returncode:
        raise ValueError(f"Unsupported QMK history: {UPSTREAM['base_commit']} must be an ancestor of {head}")
    return {"qmk_repository": UPSTREAM["repository"], "qmk_base_commit": UPSTREAM["base_commit"],
            "qmk_commit": head, "qmk_dirty": bool(git("status", "--porcelain", "--untracked-files=normal"))}


def resolve_input(label, manifest=None):
    """Resolve old workspace-relative records and relocated dependency records."""
    if not label.startswith("@"):
        return ROOT / label
    name, relative = label[1:].split("/", 1)
    roots = (manifest or {}).get("source_roots", {})
    defaults = {**BuildPaths.environment().roots(), "build": BuildPaths.environment().build}
    root = str(roots.get(name, defaults.get(name, "")))
    if not root:
        raise ValueError(f"Unknown input root: {name}")
    if os.name == "nt" and root.startswith("/mnt/") and len(root) > 7:
        root = root[5].upper() + ":/" + root[7:]
    elif os.name == "nt" and root.startswith("/"):
        distro = (manifest or {}).get("wsl_distribution", "Ubuntu")
        root = "//wsl.localhost/" + distro + root
    return (ROOT / root / relative).resolve()
