"""Verify selected builds, source inputs and all required offline evidence."""
from pathlib import Path
import argparse
import hashlib
import json
from build_config import ROOT, BuildPaths, resolve_input

TESTS = ("platform_test_results.json", "feature_test_results.json", "usb_lighting_test_results.json",
         "storage_test_results.json", "lifecycle_test_results.json", "scan_test_results.json",
         "boot_test_results.json", "eeprom_test_results.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_build(folder):
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert sha(folder / "firmware.bin") == manifest["image_sha256"]
    assert sha(folder / "application.bin") == manifest["application_sha256"]
    for item in manifest["sources"] + manifest["build_inputs"]:
        assert sha(resolve_input(item["path"], manifest)) == item["sha256"], item["path"]
    tests = []
    for filename in TESTS:
        path = folder / filename
        result = json.loads(path.read_text(encoding="utf-8"))
        assert result["status"] == "PASS_OFFLINE_NOT_FLASHED", filename
        assert result["image_sha256"] == manifest["image_sha256"], filename
        tests.append(dict(path=filename, sha256=sha(path)))
    manifest.update(status="PASS_OFFLINE_NOT_FLASHED", hardware_verified=False, offline_validation=tests)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    record = dict(build=str(folder), compiler=manifest["compiler"], code_bytes=manifest["bytes"],
                  image_sha256=manifest["image_sha256"], application_sha256=manifest["application_sha256"],
                  required_test_groups=len(tests),
                  source_inputs_verified=len(manifest["sources"]) + len(manifest["build_inputs"]))
    (folder / "verification_results.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, action="append", help="Repeat to verify several explicit builds")
    args = parser.parse_args()
    results = [verify_build((ROOT / path).resolve()) for path in (args.build_dir or [BuildPaths.environment().build])]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
