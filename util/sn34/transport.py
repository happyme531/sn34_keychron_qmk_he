# /// script
# dependencies = ["hidapi"]
# ///
"""BAT68 diagnostic transport, including explicit QMK save/restart commands."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import os
from model import load_board

import hid

class Probe:
    def __init__(self):
        usb=load_board()["usb"]
        self.tag=usb["diagnostic_tag"].encode("ascii")
        serial=os.environ.get("SN34_DEVICE_SERIAL")
        matches=[d for d in hid.enumerate(int(usb["vid"],0),int(usb["pid"],0))
                 if d["usage_page"]==0xff68 and (not serial or d.get("serial_number")==serial)]
        if len(matches)!=1:
            raise RuntimeError(f"Expected one matching diagnostic interface; found {len(matches)}. Select --keyboard and --serial.")
        self.info=matches[0]
        self.dev=hid.device()
        self.dev.open_path(self.info["path"])

    def close(self): self.dev.close()

    def query(self,command,count=0,offset=0,value=0,payload=None):
        if command not in tuple(range(0x70,0x80)):
            raise ValueError("Unsupported BAT68 probe/QMK command")
        packet=bytearray(64)
        packet[:3]=bytes((0xaa,command,count))
        if command==0x73:
            struct.pack_into("<I",packet,8,offset)
        else:
            struct.pack_into("<H",packet,3,offset)
        if command==0x75:struct.pack_into("<H",packet,8,value)
        if payload is not None:
            if len(payload)>48:raise ValueError("Payload exceeds 48 bytes")
            packet[8:8+len(payload)]=payload
        packet[5:8]=self.tag
        # Drain stale input before issuing one request. Report ID 0 is supplied
        # as the first byte to Windows hidapi, not part of the vendor payload.
        self.dev.set_nonblocking(1)
        try:
            for _ in range(32):
                if not self.dev.read(64): break
        finally:
            self.dev.set_nonblocking(0)
        n=self.dev.write(b"\0"+packet)
        if n!=65: raise RuntimeError(f"Short HID write: {n}")
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            reply=bytes(self.dev.read(64,50))
            if len(reply)==65 and reply[0]==0: reply=reply[1:]
            if len(reply)==64 and reply[:2]==bytes((0x55,command)) and reply[5:8]==self.tag:
                if reply[2]==255: raise RuntimeError("Firmware rejected command (range, held key, signature or Flash verification)")
                return reply
        raise TimeoutError("No matching BAT68 diagnostic reply")

    def identify(self):
        r=self.query(0x70)
        if r[8:12]!=b"B68P":
            return {"probe":False,"usb_version":f"0x{self.info['release_number']:04X}",
                    "product":self.info["product_string"],"note":"Stock firmware or incompatible probe; no further commands sent"}
        return {"probe":True,"protocol":r[12],"raw_slots":r[13],"electrical_positions":r[14],
                "maximum_payload":r[15],"stock_base_version":f"0x{struct.unpack_from('<H',r,16)[0]:04X}",
                "boot_region_bytes":struct.unpack_from("<H",r,18)[0],
                "stock_sha256_prefix":r[20:28].hex(),"usb_version":f"0x{self.info['release_number']:04X}"}

    def raw(self):
        values=[]
        for offset in range(0,96,24):
            r=self.query(0x71,24,offset)
            if r[2]!=48 or struct.unpack_from("<H",r,3)[0]!=offset:
                raise RuntimeError("Malformed ADC response")
            values.extend(struct.unpack_from("<24H",r,8))
        # Four packets are four snapshots, not one atomic 96-slot scan.
        return values

    def boot_dump(self):
        data=bytearray()
        for offset in range(0,8192,48):
            count=min(48,8192-offset)
            r=self.query(0x72,count,offset)
            if r[2]!=count or struct.unpack_from("<H",r,3)[0]!=offset:
                raise RuntimeError("Malformed Boot-region response")
            data.extend(r[8:8+count])
        return bytes(data)

    def app_dump(self):
        data=bytearray()
        for offset in range(0,0x7e000,48):
            count=min(48,0x7e000-offset)
            r=self.query(0x73,count,offset)
            if r[2]!=count or struct.unpack_from("<I",r,56)[0]!=offset:
                raise RuntimeError("Malformed User-ROM response")
            data.extend(r[8:8+count])
            if offset and offset//65536!=(offset+count)//65536:
                print(f"User ROM: {len(data)}/{0x7e000} bytes",flush=True)
        return bytes(data)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("identify","raw","record","dump-boot","dump-app","descriptors"))
    parser.add_argument("--seconds",type=float,default=10)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--allow-boot-read",action="store_true",help="Explicitly allow reading the possibly protected Boot region")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.worker:
        timeout=max(15,args.seconds+10) if args.command=="record" else (180 if args.command=="dump-app" else 30)
        try:
            result=subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SystemExit("USB helper timed out and was terminated")
        raise SystemExit(result.returncode)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.command=="descriptors":
        result=[]
        for item in hid.enumerate(0x0c45,0x8037):
            if item["interface_number"] not in (2,3): continue
            dev=hid.device()
            try:
                dev.open_path(item["path"])
                result.append({"interface":item["interface_number"],"usage_page":hex(item["usage_page"]),
                               "report_descriptor":bytes(dev.get_report_descriptor()).hex()})
            finally:dev.close()
        text=json.dumps(result,indent=2)
        print(text)
        if args.output:args.output.write_text(text,encoding="utf-8")
        return
    probe=Probe()
    try:
        info=probe.identify()
        print(json.dumps(info,ensure_ascii=False,indent=2),flush=True)
        if args.command=="identify": return
        if not info["probe"]: raise SystemExit("Diagnostic firmware is not active")
        if args.command=="raw":
            values=probe.raw();print(json.dumps(values))
            if args.output:args.output.write_text(json.dumps(values),encoding="utf-8")
        elif args.command=="dump-app":
            if info["protocol"]<2:parser.error("User-ROM dump requires diagnostic protocol 2")
            if not args.output:parser.error("dump-app requires --output")
            first=probe.app_dump();second=probe.app_dump()
            if first!=second:raise RuntimeError("User-ROM reads differ; no backup saved")
            args.output.write_bytes(first)
            print(json.dumps({"bytes":len(first),"sha256":hashlib.sha256(first).hexdigest(),
                              "note":"Contains the active experimental hook and extension", "output":str(args.output)}))
        elif args.command=="record":
            if not args.output: parser.error("record requires --output")
            if not 0<args.seconds<=3600: parser.error("--seconds must be between 0 and 3600")
            start=time.monotonic(); n=0
            with args.output.open("w",encoding="utf-8") as f:
                while time.monotonic()-start<args.seconds:
                    f.write(json.dumps({"t":time.monotonic()-start,"raw":probe.raw()})+"\n"); n+=1
            print(f"Recorded {n} frames to {args.output}")
        else:
            if not args.allow_boot_read: parser.error("dump-boot requires --allow-boot-read; protection may fault on real hardware")
            if not args.output: parser.error("dump-boot requires --output")
            first=probe.boot_dump(); second=probe.boot_dump()
            if first!=second: raise RuntimeError("Boot-region reads did not match; no backup saved")
            args.output.write_bytes(first)
            print(json.dumps({"bytes":len(first),"sha256":hashlib.sha256(first).hexdigest(),"output":str(args.output)}))
    finally: probe.close()

if __name__=="__main__":main()
