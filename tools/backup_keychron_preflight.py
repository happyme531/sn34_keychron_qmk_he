# /// script
# dependencies = ["hidapi"]
# ///
"""Read-only backup of the currently installed application before HE bring-up."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from bat68_probe import Probe
from bat68_qmk import status

ROOT=Path(__file__).resolve().parents[1]


def main():
    if "--worker" not in sys.argv:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,"--worker"],timeout=180).returncode)
    destination=ROOT/"backups"/datetime.now().strftime("before_keychron_he_%Y%m%d_%H%M%S")
    destination.mkdir(parents=True,exist_ok=False)
    probe=Probe()
    try:
        before=status(probe)
        if any(before["matrix"]): raise RuntimeError("Release all keys before taking a consistent preflight backup")
        boot=probe.boot_dump()
        expected=(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
        assert boot==expected,"Installed Bootloader differs from the known backup"
        (destination/"boot_8k.bin").write_bytes(boot)
        app=probe.app_dump()
        assert app[-4:]==bytes.fromhex("5555aaaa")
        (destination/"app_504k.bin").write_bytes(app)
        result=dict(status="READ_ONLY_BACKUP_COMPLETE",timestamp=datetime.now().astimezone().isoformat(),
                    device_status=before,application_sha256=hashlib.sha256(app).hexdigest(),
                    boot_sha256=hashlib.sha256(boot).hexdigest(),backup=str(destination.relative_to(ROOT)),
                    device_writes=False)
        (destination/"manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        (ROOT/"analysis/keychron_preflight_backup.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
    finally: probe.close()


if __name__=="__main__": main()
