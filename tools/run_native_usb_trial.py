# /// script
# dependencies = ["hidapi"]
# ///
"""Run the embedded native USB trial and verify return to the bridge."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import statistics
import sys
import time
from bat68_probe import Probe
from bat68_qmk import status
from hardware_registers import REGISTERS

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"analysis/native_usb_trial_hardware.json"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",action="store_true",help="Run the isolated USB trial (temporarily disconnects keyboard USB)")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.run:parser.error("Use --run to start the USB trial")
    if not args.worker:
        result=subprocess.run([sys.executable,"-u",__file__,"--run","--worker"],timeout=50)
        raise SystemExit(result.returncode)
    native=json.loads((ROOT/"build/native_usb/manifest.json").read_text())
    includes_scan=native.get("adc_scan_included",False)
    includes_keyboard=native.get("qmk_keyboard_included",False)
    output=ROOT/("analysis/native_cold_keyboard_trial_hardware.json" if includes_keyboard and native.get("cold_initialization_included") else "analysis/native_keyboard_trial_hardware.json" if includes_keyboard else "analysis/native_scan_trial_hardware.json" if includes_scan else "analysis/native_usb_trial_hardware.json")
    evidence={"status":"IN_PROGRESS","native_replies":[],"usb_products_seen":[],"adc_scan_included":includes_scan}
    def checkpoint():output.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    p=Probe()
    try:
        before=status(p);evidence["before"]=before
        assert before.get("native_usb_trial_available"),"Installed bridge has no native USB trial"
        assert not any(before["matrix"]),"Release all keys before starting the trial"
        if includes_scan:evidence["baseline_raw"]=p.raw()
        data=bytearray()
        for at in range(0,native["bytes"],48):
            count=min(48,native["bytes"]-at)
            reply=p.query(0x73,count,0x30000+at);data.extend(reply[8:8+count])
        assert hashlib.sha256(data).hexdigest()==native["image_sha256"],"Installed trial differs from tested native build"
        evidence["installed_native_sha256"]=native["image_sha256"];checkpoint()
        p.query(0x7c,payload=b"NUSB")
    finally:p.close()
    start=time.monotonic();time.sleep(0.25)
    returned=False;restart_sent=False
    while time.monotonic()-start<35:
        p=None
        try:
            p=Probe();product=p.info["product_string"]
            if product not in evidence["usb_products_seen"]:evidence["usb_products_seen"].append(product);checkpoint()
            if product=="BAT68 Native USB Trial":
                nonce=b"PING";r=p.query(0x7d,payload=nonce)
                assert r[8:12]==b"B68N" and r[36:40]==nonce
                item={"t":time.monotonic()-start,"protocol":r[12],"speed":r[14],
                    "loops":struct.unpack_from("<I",r,16)[0],"uptime_ms":struct.unpack_from("<I",r,20)[0],
                    "usb_interrupts":struct.unpack_from("<I",r,24)[0]}
                if includes_scan:
                    assert r[13]==(3 if includes_keyboard else 2),"Installed native trial mode differs from build"
                    item.update(phase=r[15],scan_frames=struct.unpack_from("<I",r,28)[0],raw=[])
                    for at in range(0,96,24):
                        raw_reply=p.query(0x7e,24,at)
                        assert raw_reply[2]==48
                        item["raw"].extend(struct.unpack_from("<24H",raw_reply,8))
                if includes_keyboard:
                    item["qmk_status"]=status(p)
                    assert item["qmk_status"]["initialized"] and item["qmk_status"]["protocol"]==5
                    assert not any(item["qmk_status"]["matrix"]),"Unexpected held key during idle verification"
                evidence["native_replies"].append(item);checkpoint()
                if len(evidence["native_replies"])%5==1:print(json.dumps({k:v for k,v in item.items() if k!="raw"}),flush=True)
                if includes_keyboard and not restart_sent and time.monotonic()-start>10:
                    p.query(0x7a,payload=b"REBT");restart_sent=True
            elif time.monotonic()-start>1:
                after=status(p)
                if after["initialized"] and after["keyboard_mode"]=="qmk":
                    evidence["after"]=after;returned=True
                    mailbox=[]
                    entries=[r for r in REGISTERS if r["name"].startswith("native_trial.")]
                    for at in range(0,len(entries),12):
                        chunk=entries[at:at+12];r=p.query(0x7b,len(chunk),chunk[0]["index"])
                        mailbox.extend(struct.unpack_from(f"<{len(chunk)}I",r,8))
                    evidence["mailbox"]=mailbox
                    break
        except (OSError,RuntimeError,TimeoutError) as exc:
            evidence["last_transport_error"]=str(exc)
        finally:
            if p:p.close()
        time.sleep(0.2)
    evidence["elapsed_seconds"]=time.monotonic()-start
    evidence["bridge_returned"]=returned
    evidence["status"]="NATIVE_USB_HARDWARE_VERIFIED" if returned and len(evidence["native_replies"])>=2 else "NATIVE_USB_TRIAL_FAILED"
    if includes_scan and len(evidence["native_replies"])>=2:
        mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
        samples=evidence["native_replies"]
        comparisons=[]
        for key in mapping:
            slot=key["raw_slot"];observed=[s["raw"][slot] for s in samples]
            median=statistics.median(observed);baseline=evidence["baseline_raw"][slot]
            comparisons.append({"key":key["name"],"raw_slot":slot,"baseline":baseline,"native_median":median,"error":abs(median-baseline),
                                "range":max(observed)-min(observed)})
        evidence["idle_comparison"]=comparisons
        frames_advance=samples[-1]["scan_frames"]>samples[0]["scan_frames"]
        stable=[c for c in comparisons if c["range"]<80]
        matches=sum(c["error"]<=40 for c in stable)
        evidence["stable_keys_with_matching_adc"]=matches
        if frames_advance and len(stable)>=60 and matches==len(stable) and returned:evidence["status"]="NATIVE_USB_AND_ADC_HARDWARE_VERIFIED"
        else:evidence["status"]="NATIVE_ADC_TRIAL_FAILED"
    if includes_keyboard and evidence["status"]=="NATIVE_USB_AND_ADC_HARDWARE_VERIFIED":evidence["native_qmk_status_verified"]=True
    checkpoint();print(json.dumps({k:v for k,v in evidence.items() if k not in ("native_replies","baseline_raw","idle_comparison")},indent=2))
    if evidence["status"] not in ("NATIVE_USB_HARDWARE_VERIFIED","NATIVE_USB_AND_ADC_HARDWARE_VERIFIED"):raise SystemExit(1)

if __name__=="__main__":main()
