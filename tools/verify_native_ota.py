# /// script
# dependencies = ["hidapi"]
# ///
"""Verify native -> retained factory Boot -> existing official OTA -> bridge."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import hid
from bat68_probe import Probe
from bat68_qmk import status
from verify_native_persistence import enter_native

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"analysis/native_ota_hardware.json"
def main():
    if "--worker" not in sys.argv:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,"--worker"],timeout=75).returncode)
    native=json.loads((ROOT/"build/native_usb/manifest.json").read_text())
    evidence={"status":"IN_PROGRESS","native_sha256":native["image_sha256"],"usb_transitions":[]}
    def checkpoint():OUTPUT.write_text(json.dumps(evidence,indent=2))
    p=Probe()
    try:
        p,before=enter_native(p);assert before["protocol"]==5
        data=bytearray()
        for at in range(0,native["bytes"],48):
            count=min(48,native["bytes"]-at);data.extend(p.query(0x73,count,0x30000+at)[8:8+count])
        assert hashlib.sha256(data).hexdigest()==native["image_sha256"]
        evidence["before"]=before;evidence["before_product"]=p.info["product_string"]
        assert evidence["before_product"]=="BAT68 Native USB Trial"
        original_boot=(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
        assert p.boot_dump()==original_boot
        evidence["boot_sha256_before"]=hashlib.sha256(original_boot).hexdigest();checkpoint()
    finally:p.close()
    # This is the same original GUI and validated resource wrapper used for
    # previous flashes. Observe identities only; do not open the Boot device.
    start=time.monotonic();last=None
    command=[r"C:\Program Files\PowerShell\7\pwsh.exe","-NoProfile","-File",str(ROOT/"tools/oem_qmk_ota.ps1"),"-StartUpdate","-Generation","v15"]
    proc=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
    while proc.poll() is None and time.monotonic()-start<60:
        identities=sorted({(d["product_id"],d.get("product_string","")) for d in hid.enumerate(0x0c45,0)})
        if identities!=last:
            item={"t":time.monotonic()-start,"devices":[{"pid":hex(pid),"product":name} for pid,name in identities]}
            evidence["usb_transitions"].append(item);checkpoint();print(json.dumps(item),flush=True);last=identities
        time.sleep(0.05)
    if proc.poll() is None:
        proc.terminate();proc.wait(timeout=5);raise TimeoutError("Official OTA helper exceeded its bounded observation deadline")
    stdout,stderr=proc.communicate();evidence["ota_exit_code"]=proc.returncode
    evidence["ota_stdout"]=stdout;evidence["ota_stderr"]=stderr
    result_path=ROOT/"analysis/qmk_v15_ota_result.json"
    if result_path.exists():evidence["ota_result"]=json.loads(result_path.read_text(encoding="utf-8-sig"))
    checkpoint()
    assert proc.returncode==0,(stdout,stderr)
    assert any(d["pid"]=="0x7210" for item in evidence["usb_transitions"] for d in item["devices"]),"Boot USB identity was not observed"
    p=Probe()
    try:
        evidence["after"]=status(p)
        assert evidence["after"]["protocol"]==4 and evidence["after"]["initialized"]
        boot=p.boot_dump();assert boot==original_boot
        evidence["boot_sha256_after"]=hashlib.sha256(boot).hexdigest()
    finally:p.close()
    evidence["status"]="NATIVE_OTA_HANDOFF_AND_UPDATE_VERIFIED";checkpoint()
    print(json.dumps(evidence,indent=2))

if __name__=="__main__":main()
