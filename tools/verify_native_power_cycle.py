# /// script
# dependencies = ["hidapi"]
# ///
"""Observe a physical disconnect/reconnect and verify standalone cold startup."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import hid
from bat68_probe import Probe
from bat68_qmk import status

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"analysis/native_power_cycle_hardware.json"
def main():
    if "--worker" not in sys.argv:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,"--worker"],timeout=190).returncode)
    manifest=json.loads((ROOT/"build/native_app/manifest.json").read_text())
    evidence={"status":"WAITING_FOR_PHYSICAL_POWER_CYCLE","source_code_sha256":manifest["image_sha256"]}
    def checkpoint():OUTPUT.write_text(json.dumps(evidence,indent=2))
    p=Probe()
    try:
        before=status(p);assert before["protocol"]==6
        evidence["before"]=before
        identity=p.query(0x7d,payload=b"COLD");evidence["uptime_before_ms"]=struct.unpack_from("<I",identity,20)[0]
    finally:p.close()
    checkpoint();print("READY: watching for keyboard USB removal and return",flush=True)
    start=time.monotonic();disconnected_at=None
    while time.monotonic()-start<180:
        devices=hid.enumerate(0x0c45,0x8037)
        if not devices:
            if disconnected_at is None:
                disconnected_at=time.monotonic();evidence["disconnect_t"]=disconnected_at-start;checkpoint();print("USB removal observed",flush=True)
        elif disconnected_at is not None:
            p=None
            try:
                p=Probe();after=status(p)
                assert after["protocol"]==6 and after["initialized"] and p.info["product_string"]=="BAT68 QMK"
                identity=p.query(0x7d,payload=b"COLD")
                assert identity[36:40]==b"COLD" and identity[52]==1 and identity[53]==0
                assert struct.unpack_from("<I",identity,40)[0]==192000000
                assert struct.unpack_from("<I",identity,44)[0]==0
                assert struct.unpack_from("<I",identity,48)[0]==0xaaaa5555
                assert after["saved_sequence"]==before["saved_sequence"]
                code=bytearray()
                for at in range(0,manifest["bytes"],48):
                    count=min(48,manifest["bytes"]-at);code.extend(p.query(0x73,count,at)[8:8+count])
                assert hashlib.sha256(code).hexdigest()==manifest["image_sha256"]
                boot=p.boot_dump();assert boot==(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
                evidence.update(status="NATIVE_COLD_POWER_CYCLE_HARDWARE_VERIFIED",after=after,
                                return_t=time.monotonic()-start,uptime_after_ms=struct.unpack_from("<I",identity,20)[0],
                                boot_sha256=hashlib.sha256(boot).hexdigest())
                checkpoint();print(json.dumps(evidence,indent=2));return
            except (OSError,RuntimeError,TimeoutError):pass
            finally:
                if p:p.close()
        time.sleep(0.05)
    evidence["status"]="POWER_CYCLE_NOT_OBSERVED_OR_RETURN_NOT_VERIFIED";checkpoint();raise TimeoutError(evidence["status"])

if __name__=="__main__":main()
