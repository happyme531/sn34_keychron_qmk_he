# /// script
# dependencies = ["hidapi"]
# ///
"""Non-flashing USB ISP round trip: enter, read version/checksum, leave.

Only three ISP commands exist in this tool. No erase, program, security change,
code-option write, or arbitrary command facility is implemented.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

import hid

VID=0x0c45
APP_PID=0x8037
BOOT_PID=0x7210
MAGIC=bytes.fromhex("aa55a55aff0033cc")
COMMANDS={"version":1,"checksum":6,"return-user":7}

def describe(d):
    return {k:(v.decode(errors="replace") if isinstance(v,bytes) else v) for k,v in d.items()}

def feature_frame(name):
    command=COMMANDS[name]
    packet=bytearray(65)
    packet[1:4]=bytes((command,0xaa,0x55))
    return bytes(packet)

def exchange(dev,name,log):
    frame=feature_frame(name)
    log.append({"action":"feature-send","operation":name,"data":frame.hex()})
    dev.send_feature_report(frame)
    if name=="return-user":return None
    time.sleep(0.06)
    reply=bytes(dev.get_feature_report(0,65))
    log.append({"action":"feature-receive","operation":name,"data":reply.hex()})
    payload=reply[1:] if len(reply)==65 and reply[0]==0 else reply
    if len(payload)<16 or payload[:4]!=frame[1:5] or payload[4:8]!=b"\xfa"*4:
        raise RuntimeError(f"Unexpected {name} reply: {reply.hex()}")
    return payload

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("analysis/usb_isp_roundtrip.json"))
    parser.add_argument("--enter",action="store_true",help="Request a temporary jump into ISP, then return to application")
    parser.add_argument("--attach",action="store_true",help="Query an already-entered ISP interface without sending the entry magic")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.worker:
        try:
            r=subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],
                             timeout=20,capture_output=True,text=True,encoding="utf-8")
        except subprocess.TimeoutExpired:
            raise SystemExit("Native HID helper timed out and was terminated; inspect the saved log")
        print(r.stdout,end="")
        print(r.stderr,end="",file=sys.stderr)
        raise SystemExit(r.returncode)
    log=[]
    result={"operations_allowlist":COMMANDS,"flash_operations_present":False,"log":log}
    app=[d for d in hid.enumerate(VID,APP_PID) if d["interface_number"]==3 and d["usage_page"]==0xff67]
    result["app_before"]=[describe(d) for d in app]
    if not args.enter and not args.attach:
        print(json.dumps(result,indent=2));return
    if args.enter and len(app)!=1:raise RuntimeError(f"Expected exactly one BAT68 ISP feature interface; found {len(app)}")
    dev=None
    entered=False
    boot=None
    try:
        if args.enter:
            dev=hid.device();dev.open_path(app[0]["path"])
            packet=b"\0"+MAGIC+bytes(64-len(MAGIC))
            log.append({"action":"feature-send","operation":"enter-ISP","data":packet.hex()})
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            sent=dev.send_feature_report(packet)
            result["enter_bytes_sent"]=sent
            dev.close();dev=None
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            devices=hid.enumerate(VID,0)
            candidates=[d for d in devices if d["product_id"]==BOOT_PID]
            if candidates:
                result["boot_devices"]=[describe(d) for d in candidates]
                # Bootloader is a vendor-defined HID. Never open keyboard/mouse collections.
                vendor=[d for d in candidates if d["usage_page"]>=0xff00]
                if len(vendor)==1:
                    boot=vendor[0];break
                if len(vendor)>1:
                    raise RuntimeError("Multiple Bootloader vendor interfaces; manual selection is required")
            if args.attach:break
            time.sleep(0.1)
        if boot is None:
            raise RuntimeError("OEM 0C45:7210 Boot interface did not enumerate; no stale application HID will be queried")
        dev=hid.device();dev.open_path(boot["path"])
        result["boot_report_descriptor"]=bytes(dev.get_report_descriptor()).hex()
        version=exchange(dev,"version",log)
        entered=True
        result["version_payload"]=version.hex()
        result["identity_bytes"]=list(version[8:16])
        try:
            check=exchange(dev,"checksum",log)
            result["user_checksum"]=f"0x{struct.unpack_from('<H',check,8)[0]:04X}"
        except Exception as e:
            result["checksum_error"]=str(e)
    except Exception as e:
        result["error"]=str(e)
    finally:
        if entered and dev is not None:
            try:
                exchange(dev,"return-user",log)
                result["return_requested"]=True
            except Exception as e:result["return_error"]=str(e)
        if dev is not None:dev.close()
        if entered:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                returned=[d for d in hid.enumerate(VID,APP_PID) if d["interface_number"]==2 and d["product_string"]=="EWEADN BAT68"]
                if returned:
                    result["app_returned"]=[describe(d) for d in returned];break
                time.sleep(0.1)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    if "error" in result or not result.get("app_returned"):
        raise SystemExit(1)

if __name__=="__main__":main()
