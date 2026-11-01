# /// script
# dependencies = ["hidapi"]
# ///
"""Verify the complete source-built application on the connected keyboard."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import time
from bat68_probe import Probe
from bat68_qmk import status

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation",default="v16")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    assert args.generation.startswith("v") and args.generation[1:].isdigit()
    if not args.worker:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=180).returncode)
    manifest=json.loads((ROOT/"build/native_app/manifest.json").read_text())
    output=ROOT/f"analysis/native_app_{args.generation}_hardware.json"
    backup=ROOT/f"backups/native_{args.generation}_20261030";backup.mkdir(parents=True,exist_ok=True)
    evidence={"status":"IN_PROGRESS","source_code_sha256":manifest["image_sha256"],"application_sha256":manifest["application_sha256"],"checks":[]}
    def record(name,**details):
        item={"check":name,**details};evidence["checks"].append(item)
        output.write_text(json.dumps(evidence,indent=2));print(json.dumps(item),flush=True)
    p=Probe()
    try:
        before=status(p);assert before["protocol"]==6 and before["initialized"] and not any(before["matrix"])
        assert p.info["product_string"]=="BAT68 QMK"
        record("Complete native application owns reset and keyboard",usb_product=p.info["product_string"],status=before)
        data=bytearray()
        for at in range(0,manifest["bytes"],48):
            count=min(48,manifest["bytes"]-at);data.extend(p.query(0x73,count,at)[8:8+count])
        assert hashlib.sha256(data).hexdigest()==manifest["image_sha256"]
        record("Live executable bytes exactly match the source-linked image",bytes=len(data))
        ping=p.query(0x7d,payload=b"PING")
        assert ping[8:12]==b"B68N" and ping[13]==4 and ping[36:40]==b"PING" and ping[52]==1
        assert struct.unpack_from("<I",ping,40)[0]==192000000 and struct.unpack_from("<I",ping,44)[0]==0
        record("Native startup and USB report successful 192 MHz standalone initialization",hclk_hz=192000000,bringup_guard=bool(ping[53]),footer=hex(struct.unpack_from("<I",ping,48)[0]))
        profile=json.loads((ROOT/"analysis/hall_board_profile.json").read_text())["keys"]
        samples=[]
        for _ in range(8):samples.append(p.raw());time.sleep(0.05)
        errors=[abs(statistics.median(sample[k["raw_slot"]] for sample in samples)-k["idle"]) for k in profile]
        assert max(errors)<=60,errors
        assert not any(status(p)["matrix"])
        record("All 67 Hall inputs agree with the measured board references and report no idle presses",keys=len(errors),maximum_idle_error=max(errors))
        boot=p.boot_dump();assert p.boot_dump()==boot
        expected_boot=(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
        assert boot==expected_boot;(backup/"boot_00200000_8k.bin").write_bytes(boot)
        record("Retained Bootloader read twice and unchanged",sha256=hashlib.sha256(boot).hexdigest())
        if manifest["bringup_guard_enabled"]:
            result=p.query(0x7b,payload=b"CMT!");assert result[8]==1
            record("Bring-up guard committed after executable, startup, USB, ADC and Boot checks")
        footer=p.query(0x73,4,0x7dffc)[8:12];assert footer==bytes.fromhex("5555aaaa")
        first=p.app_dump();second=p.app_dump();assert first==second
        assert hashlib.sha256(first).hexdigest()==manifest["application_sha256"]
        assert first==(ROOT/"build/native_app/bat68_native_app.bin").read_bytes()
        (backup/"app_504k.bin").write_bytes(first)
        record("Entire 504 KiB live User ROM read twice and exactly matches the source-built complete application",bytes=len(first),sha256=hashlib.sha256(first).hexdigest(),original_application_bytes=0)
        evidence["status"]="COMPLETE_NATIVE_APPLICATION_HARDWARE_VERIFIED"
        output.write_text(json.dumps(evidence,indent=2));print(evidence["status"])
    finally:p.close()

if __name__=="__main__":main()
