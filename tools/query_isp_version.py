# /// script
# dependencies = ["hidapi"]
# ///
"""Only issue the OEM read-only version request; never enter ISP or write Flash."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pid",type=lambda s:int(s,0),choices=(0x8037,0x7210),default=0x8037)
    p.add_argument("--output",type=Path,default=Path("analysis/usb_version_in_app.json"))
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=p.parse_args()
    if not args.worker:
        try:
            r=subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],
                             timeout=8,capture_output=True,text=True,encoding="utf-8")
        except subprocess.TimeoutExpired:
            result=json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
            result["error"]="Native HID helper timed out and was terminated"
            args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result,indent=2))
            raise SystemExit(1)
        print(r.stdout,end="")
        print(r.stderr,end="",file=sys.stderr)
        raise SystemExit(r.returncode)
    import hid
    result={"operation":"version-only", "enter_isp":False,"flash_operations_present":False,"pid":hex(args.pid),"stage":"enumerating"}
    def save():
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    save()
    devices=hid.enumerate(0x0c45,args.pid)
    devices=[d for d in devices if d["usage_page"]>=0xff00 and
             (args.pid==0x7210 or (d["interface_number"]==3 and d["product_string"]=="EWEADN BAT68"))]
    if len(devices)!=1:
        raise RuntimeError(f"Expected one matching feature interface, found {len(devices)}")
    path=devices[0]["path"]
    result["path"]=path.decode()
    packet=b"\x00\x01\xaa\x55\x00"+bytes(60)
    result["request"]=packet.hex()
    dev=hid.device()
    try:
        result["stage"]="opening";save()
        dev.open_path(path)
        result["stage"]="sending";save()
        result["sent"]=dev.send_feature_report(packet)
    finally:
        dev.close()
    time.sleep(0.01)
    dev=hid.device()
    try:
        result["stage"]="reading";save()
        dev.open_path(path)
        reply=bytes(dev.get_feature_report(0,65))
        result["reply"]=reply.hex()
        payload=reply[1:] if len(reply)==65 and reply[0]==0 else reply
        result["valid_echo"]=payload[:4]==packet[1:5]
        result["valid_sn34_protocol_response"]=(result["valid_echo"] and payload[4:8]==b"\xfa"*4
                                               and payload[8:10]==bytes((0x20,0x08)))
        result["version_data"]=payload[8:16].hex() if result["valid_echo"] else None
        result["stage"]="finished";save()
    finally:
        dev.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
