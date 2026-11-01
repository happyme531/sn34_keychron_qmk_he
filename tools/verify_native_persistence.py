# /// script
# dependencies = ["hidapi"]
# ///
"""Verify the native SDK Flash backend by changing an unconnected position."""
import json
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from bat68_probe import Probe
from bat68_qmk import status,save,restart

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"analysis/native_persistence_hardware.json"

def enter_native(p):
    assert status(p)["native_usb_trial_available"]
    assert not any(status(p)["matrix"])
    p.query(0x7c,payload=b"NUSB");p.close();time.sleep(0.5)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        q=None
        try:
            q=Probe();s=status(q)
            if s["protocol"]==5:return q,s
        except (OSError,RuntimeError,TimeoutError):pass
        if q:q.close()
        time.sleep(0.2)
    raise TimeoutError("Native keyboard did not enumerate")

def read_pages(p):
    pages=[]
    for page in (0x7d000,0x7d200):
        data=bytearray()
        for at in range(0,512,48):
            count=min(48,512-at);r=p.query(0x73,count,page+at);data.extend(r[8:8+count])
        assert data[:4]==b"B68K" and struct.unpack_from("<I",data,404)[0]==0xc0deb68a
        assert zlib.crc32(data[:400])==struct.unpack_from("<I",data,400)[0]
        pages.append({"user_offset":hex(page),"sequence":struct.unpack_from("<I",data,8)[0],"crc_valid":True,"unused_keycode":struct.unpack_from("<H",data,16)[0]})
    return pages

def main():
    standalone="--standalone" in sys.argv
    if "--worker" not in sys.argv:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=45).returncode)
    output=ROOT/("analysis/native_standalone_persistence_hardware.json" if standalone else "analysis/native_persistence_hardware.json")
    report={"status":"IN_PROGRESS","checks":[],"uses_unconnected_position":True}
    mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
    assert all(k["raw_slot"]!=0 for k in mapping)
    def record(name,**details):
        item={"check":name,**details};report["checks"].append(item)
        output.write_text(json.dumps(report,indent=2));print(json.dumps(item),flush=True)
    p=Probe()
    original=None
    try:
        original=struct.unpack_from("<H",p.query(0x76,0,0),8)[0]
        if standalone:
            info=status(p);assert info["protocol"]==6 and not any(info["matrix"])
        else:p,info=enter_native(p)
        record("Native source-built keyboard active",status=info)
        modified=4 if original!=4 else 5
        assert struct.unpack_from("<H",p.query(0x76,0,0),8)[0]==original
        p.query(0x75,0,0,modified)
        result=save(p);assert result["flash_written"] and not result["status"]["unsaved_changes"]
        record("Native SDK HAL persisted changed unused position",result=result)
        assert not save(p)["flash_written"]
        p,info=restart(p)
        assert info["protocol"]==(6 if standalone else 4) and struct.unpack_from("<H",p.query(0x76,0,0),8)[0]==modified
        record("Saved record loads after reset in standalone application" if standalone else "Saved native record also loads after reset in bridge",status=info)
        if not standalone:p,info=enter_native(p)
        assert struct.unpack_from("<H",p.query(0x76,0,0),8)[0]==modified
        record("Native startup independently reloads persisted mapping",status=info)
        p.query(0x75,0,0,original);restored=save(p);assert restored["flash_written"]
        record("Original unused mapping restored with native SDK HAL",result=restored)
        pages=read_pages(p);record("Both settings pages have valid CRC and commit",pages=pages)
        p,info=restart(p)
        assert struct.unpack_from("<H",p.query(0x76,0,0),8)[0]==original
        record("Reset returns to working QMK with original mapping",status=info)
        report["status"]="NATIVE_PERSISTENCE_HARDWARE_VERIFIED"
        output.write_text(json.dumps(report,indent=2));print(report["status"])
    finally:
        if p:p.close()

if __name__=="__main__":main()
