"""Build infrastructure regressions: patch failures, provenance and relocation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

from dataclasses import replace
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from build_config import BuildPaths, ROOT, UPSTREAM, qmk_revision, resolve_input
from patches import apply_series
from prepare import prepare


class BuildInfrastructure(unittest.TestCase):
    def setUp(self):
        (ROOT / ".build").mkdir(exist_ok=True)
        self.temporary = TemporaryDirectory(prefix="build-test-", dir=ROOT / ".build")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_patch_is_checked_and_only_generated_copy_is_modified(self):
        source = self.folder / "source"
        source.mkdir()
        original = b"first\r\nold\r\nlast\r\n"
        (source / "input.c").write_bytes(original)
        series = self.folder / "patches"
        series.mkdir()
        (series / "series.json").write_text(json.dumps([{"file": "fix.patch", "purpose": "regression test"}]))
        (series / "fix.patch").write_text("--- a/input.c\n+++ b/input.c\n@@ -1,3 +1,3 @@\n first\n-old\n+new\n last\n")
        output = self.folder / "output"
        files, record = apply_series(source, ["input.c"], output, series)
        self.assertEqual((source / "input.c").read_bytes(), original)
        self.assertEqual(files["input.c"].read_bytes(), b"first\nnew\nlast\n")
        self.assertNotEqual(record["inputs"][0]["original_sha256"], record["inputs"][0]["patched_sha256"])
        timestamp = files["input.c"].stat().st_mtime_ns
        apply_series(source, ["input.c"], output, series)
        self.assertEqual(timestamp, files["input.c"].stat().st_mtime_ns)
        (source / "input.c").write_text("incompatible upstream\n")
        with self.assertRaisesRegex(RuntimeError, "Patch does not match"):
            apply_series(source, ["input.c"], output, series)
        self.assertEqual(files["input.c"].read_bytes(), b"first\nnew\nlast\n")

    def test_committed_fork_descendants_are_accepted(self):
        repo = self.folder / "qmk-fork"
        repo.mkdir()

        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

        git("init", "-q")
        for message in ("base", "board port"):
            git("-c", "user.name=Build test", "-c", "user.email=build-test@example.invalid",
                "commit", "--allow-empty", "-qm", message)
            if message == "base":
                base = git("rev-parse", "HEAD")
        with patch.dict(UPSTREAM, {"base_commit": base}):
            record = qmk_revision(repo)
        self.assertEqual(record["qmk_base_commit"], base)
        self.assertNotEqual(record["qmk_commit"], base)
        self.assertFalse(record["qmk_dirty"])
        with patch.dict(UPSTREAM, {"base_commit": "f" * 40}):
            with self.assertRaisesRegex(ValueError, "Unsupported QMK history"):
                qmk_revision(repo)

    def test_external_dependency_records_resolve_after_relocation(self):
        qmk = ROOT.parent / "external-qmk-build-test"
        locations = replace(BuildPaths.environment(), qmk=qmk)
        label = locations.label(qmk / "quantum/keyboard.c")
        self.assertEqual(label, "@qmk/quantum/keyboard.c")
        self.assertEqual(resolve_input(label, {"source_roots": locations.serialized_roots()}), qmk / "quantum/keyboard.c")

    def test_failed_preparation_invalidates_stale_make_include(self):
        locations = replace(BuildPaths.environment(), build=self.folder / "generated")
        locations.build.mkdir()
        include = locations.build / "platform_sources.mk"
        include.write_text("SN34_EXTRA_SRC := stale.c\n")
        with patch("prepare.apply_series", side_effect=RuntimeError("upstream changed")):
            with self.assertRaisesRegex(RuntimeError, "upstream changed"):
                prepare(locations)
        self.assertTrue(include.read_text().startswith("$(error SN34 preparation incomplete"))


if __name__ == "__main__":
    unittest.main()
