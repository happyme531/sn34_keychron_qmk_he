"""Apply checked-in unified diffs to generated copies, never to dependencies."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import subprocess
from build_config import ROOT, write_if_changed


def apply_series(source, inputs, destination, series_dir):
    """Stage and check each patch before publishing any generated source."""
    destination.mkdir(parents=True, exist_ok=True)
    series_path = series_dir / "series.json"
    series = json.loads(series_path.read_text(encoding="utf-8"))
    records = []
    # Only the newly created staging directory under the explicit build
    # destination is removed; dependency and source trees are never removed.
    with TemporaryDirectory(prefix="patch-stage-", dir=destination) as temporary:
        stage = Path(temporary)
        originals = {}
        for relative in inputs:
            data = (source / relative).read_text(encoding="utf-8").encode("utf-8")
            originals[relative] = hashlib.sha256((source / relative).read_bytes()).hexdigest()
            write_if_changed(stage / relative, data)
        for entry in series:
            patch = series_dir / entry["file"]
            command = ["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn"]
            patch_data = patch.read_text(encoding="utf-8").encode("utf-8")
            check = subprocess.run([*command, "--check"], input=patch_data, cwd=stage, capture_output=True)
            if check.returncode:
                detail = check.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Patch does not match its input: {patch.relative_to(ROOT)}\n{detail}")
            subprocess.run(command, input=patch_data, cwd=stage, check=True, capture_output=True)
            records.append({"patch": patch.relative_to(ROOT).as_posix(),
                            "sha256": hashlib.sha256(patch.read_bytes()).hexdigest(), "purpose": entry["purpose"]})
        files = {}
        for relative in inputs:
            generated = destination / relative
            write_if_changed(generated, (stage / relative).read_bytes())
            files[relative] = generated
    return files, {"series": series_path.relative_to(ROOT).as_posix(), "patches": records,
                   "inputs": [{"path": path, "original_sha256": sha,
                               "patched_sha256": hashlib.sha256(files[path].read_bytes()).hexdigest()}
                              for path, sha in sorted(originals.items())]}
