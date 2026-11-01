# /// script
# dependencies = ["hidapi"]
# ///
"""Enter the installed native trial and leave it active for focused key testing."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from bat68_probe import Probe
from verify_native_persistence import enter_native

def main():
    if "--worker" not in sys.argv:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,"--worker"],timeout=20).returncode)
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/"build/native_usb/manifest.json").read_text())
    p=Probe()
    try:
        data=bytearray()
        for at in range(0,manifest["bytes"],48):
            count=min(48,manifest["bytes"]-at);r=p.query(0x73,count,0x30000+at);data.extend(r[8:8+count])
        assert hashlib.sha256(data).hexdigest()==manifest["image_sha256"]
        p,s=enter_native(p)
        result={"time_unix":time.time(),"image_sha256":manifest["image_sha256"],"trial_milliseconds":manifest["trial_milliseconds"],"status":s}
        (root/"analysis/native_manual_trial_start.json").write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    finally:p.close()

if __name__=="__main__":main()
