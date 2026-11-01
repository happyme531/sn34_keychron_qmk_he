# /// script
# dependencies = ["hidapi"]
# ///
"""Observe standalone -> original Boot -> original OTA -> standalone, read Boot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import hid
from bat68_probe import Probe
from bat68_qmk import status

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation",default="v17")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args();assert args.generation.startswith("v") and args.generation[1:].isdigit()
    if not args.worker:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=80).returncode)
    target=json.loads((ROOT/"build/native_app/manifest.json").read_text())
    output=ROOT/f"analysis/native_app_{args.generation}_ota_hardware.json"
    evidence={"status":"IN_PROGRESS","target_application_sha256":target["application_sha256"],"usb_transitions":[]}
    def checkpoint():output.write_text(json.dumps(evidence,indent=2))
    p=Probe()
    try:
        before=status(p);assert before["protocol"]==6 and before["initialized"] and not any(before["matrix"])
        evidence["before"]=before;assert p.info["product_string"]=="BAT68 QMK"
        before_id=p.query(0x7d,payload=b"PING");assert before_id[13]==4 and before_id[52]==1
        expected_boot=(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
        boot=p.boot_dump();assert boot==expected_boot
        evidence["boot_sha256_before"]=hashlib.sha256(boot).hexdigest();checkpoint()
    finally:p.close()
    command=[r"C:\Program Files\PowerShell\7\pwsh.exe","-NoProfile","-File",str(ROOT/"tools/oem_native_ota.ps1"),"-StartUpdate","-Generation",args.generation]
    start=time.monotonic();last=None
    proc=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
    while proc.poll() is None and time.monotonic()-start<65:
        devices=sorted({(d["product_id"],d.get("product_string","")) for d in hid.enumerate(0x0c45,0)})
        if devices!=last:
            item={"t":time.monotonic()-start,"devices":[{"pid":hex(pid),"product":name} for pid,name in devices]}
            evidence["usb_transitions"].append(item);checkpoint();print(json.dumps(item),flush=True);last=devices
        time.sleep(0.05)
    if proc.poll() is None:proc.terminate();proc.wait(timeout=5);raise TimeoutError("Official GUI helper did not finish")
    stdout,stderr=proc.communicate();evidence.update(ota_exit_code=proc.returncode,ota_stdout=stdout,ota_stderr=stderr)
    ota_path=ROOT/f"analysis/qmk_{args.generation}_ota_result.json"
    if ota_path.exists():evidence["ota_result"]=json.loads(ota_path.read_text(encoding="utf-8-sig"))
    checkpoint();assert proc.returncode==0,(stdout,stderr)
    assert any(d["pid"]=="0x7210" for state in evidence["usb_transitions"] for d in state["devices"])
    p=Probe()
    try:
        after=status(p);assert after["protocol"]==6 and after["initialized"]
        evidence["after"]=after
        native_id=p.query(0x7d,payload=b"PING");assert native_id[52]==1 and bool(native_id[53])==target["bringup_guard_enabled"]
        data=bytearray()
        for at in range(0,target["bytes"],48):
            count=min(48,target["bytes"]-at);data.extend(p.query(0x73,count,at)[8:8+count])
        assert hashlib.sha256(data).hexdigest()==target["image_sha256"]
        evidence["live_code_sha256_after"]=hashlib.sha256(data).hexdigest()
        boot=p.boot_dump();assert boot==expected_boot
        evidence["boot_sha256_after"]=hashlib.sha256(boot).hexdigest()
    finally:p.close()
    evidence["status"]="COMPLETE_NATIVE_OTA_AND_BOOT_PRESERVATION_VERIFIED";checkpoint();print(json.dumps(evidence,indent=2))

if __name__=="__main__":main()
