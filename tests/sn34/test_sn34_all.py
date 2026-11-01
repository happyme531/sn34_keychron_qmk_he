# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Run all production offline checks against one explicit build directory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import argparse
import os
from pathlib import Path
import subprocess
import sys
from build_config import ROOT, BuildPaths
from verify_artifacts import verify_build

TESTS = ("test_bat68.py", "test_sn34_features.py", "test_sn34_usb.py", "test_storage.py",
         "test_sn34_lifecycle.py", "test_native_scan.py", "test_native_boot.py", "test_keychron_eeprom.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=BuildPaths.environment().build)
    args = parser.parse_args()
    build = (ROOT / args.build_dir).resolve()
    env = {**os.environ, "SN34_NATIVE_BUILD": str(build)}
    logs = build / "test_logs"
    logs.mkdir(exist_ok=True)
    for name in TESTS:
        log = logs / (Path(name).stem + ".log")
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run([sys.executable, str(ROOT / "tests/sn34" / name)], cwd=ROOT,
                                    env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text(encoding="utf-8"))
            raise SystemExit(f"FAIL {name}; log: {log}")
        print(f"PASS {name}", flush=True)
    record = verify_build(build)
    print(f"Verified {record['required_test_groups']} groups and {record['source_inputs_verified']} inputs: {build}")


if __name__ == "__main__":
    main()
