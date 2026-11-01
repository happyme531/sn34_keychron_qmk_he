# /// script
# dependencies = ["hidapi"]
# ///
"""Plan/preflight/stage the v1.18 probe in ONE unused Flash page over USB.

Default: offline plan only. --preflight: read-only USB checks and page backups.
--stage-extension: explicitly program the unused 0x18000 page, verify each chunk.
This tool CANNOT activate a hook, modify Boot/option/calibration pages, or enter ISP.
The probe remains inactive after staging. CPU still executes original firmware.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/"build/v118"
PAGE=0x18000
PAGE_SIZE=512
HOOK_PAGE=0xea00
READ_BASE=0x9200
WRITE_BASE=0x9a00  # Exact v1.18 dispatch command 0x24, no settings reload hook.
SOURCE_SHA="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36"
LIVE_SHA="1e061405c9b44d85af7fabfe1fc6cbcff4c5c78cebd70adbd3e53d80b71d2252"

def digest(data):return hashlib.sha256(data).hexdigest()

def write_frame(address,data):
    # Keep this guard INSIDE packet construction: even internal callers cannot
    # target executable firmware, Boot, options, or any page except the spare one.
    if not 0<len(data)<=48 or not PAGE<=address or address+len(data)>PAGE+PAGE_SIZE:
        raise ValueError("Only 1..48 bytes within unused page 0x18000 are writable")
    if address//PAGE_SIZE != (address+len(data)-1)//PAGE_SIZE:
        raise ValueError("Cross-page write forbidden")
    packet=bytearray(64)
    packet[:3]=bytes((0xaa,0x24,len(data)))
    struct.pack_into("<H",packet,3,address-WRITE_BASE)
    packet[5:8]=b"STG"
    packet[8:8+len(data)]=data
    return bytes(packet)

def inputs():
    stock=(ROOT/"analysis/v118_rcdata_4000.bin").read_bytes()
    live=(ROOT/"analysis/live_v118_window_clean_a.bin").read_bytes()
    second=(ROOT/"analysis/live_v118_window_clean_b.bin").read_bytes()
    ext=(BUILD/"probe_extension.bin").read_bytes()
    manifest=json.loads((BUILD/"probe_manifest.json").read_text())
    tests=json.loads((BUILD/"probe_test_results.json").read_text())
    image=(BUILD/"bat68_probe_stock_v118.bin").read_bytes()
    if digest(stock)!=SOURCE_SHA or digest(live)!=LIVE_SHA or live!=second:
        raise RuntimeError("Pinned source or independent live reads changed")
    if tests["status"]!="PASS_OFFLINE_ONLY" or digest(image)!=tests["image_sha256"] or digest(image)!=manifest["image_sha256"]:
        raise RuntimeError("Experimental image has not passed its exact ARM tests")
    if len(ext)>PAGE_SIZE or any(stock[PAGE:PAGE+PAGE_SIZE]):
        raise RuntimeError("Extension does not fit in the known empty stock page")
    if image[PAGE:PAGE+len(ext)]!=ext:
        raise RuntimeError("Extension does not match the tested image")
    for at in (PAGE,HOOK_PAGE):
        if live[at-READ_BASE:at-READ_BASE+PAGE_SIZE]!=stock[at:at+PAGE_SIZE]:
            raise RuntimeError(f"Live page {at:#x} differs from the pinned stock page")
    target=ext+bytes(PAGE_SIZE-len(ext))
    frames=[write_frame(PAGE+i,ext[i:i+48]) for i in range(0,len(ext),48)]
    plan={"status":"NOT_EXECUTED", "method":"Normal v1.18 HID config command 0x24; no ISP jump",
          "only_writable_page":hex(PAGE),"page_bytes":PAGE_SIZE,"payload_bytes":len(ext),
          "before_sha256":digest(bytes(PAGE_SIZE)),"after_sha256":digest(target),
          "packets":len(frames),"probe_activated":False,"active_hook_write_implemented":False,
          "stock_image_sha256":SOURCE_SHA,"tested_probe_image_sha256":digest(image),
          "writes":[{"address":hex(PAGE+i*48),"report_payload":frame.hex()} for i,frame in enumerate(frames)],
          "limitations":["Actual Flash hardware behavior remains untested", "USB recovery Bootloader has not been demonstrated",
                         "This stages inactive code only; activation requires a separate reviewed step"]}
    return stock,target,frames,plan

class StockConfig:
    def __init__(self):
        import hid
        matches=[d for d in hid.enumerate(0x0c45,0x8037) if d["interface_number"]==2
                 and d["usage_page"]==0xff68 and d["product_string"]=="EWEADN BAT68"
                 and d["release_number"]==0x0118]
        if len(matches)!=1:raise RuntimeError("Expected exactly one responding stock BAT68 v1.18")
        self.dev=hid.device();self.dev.open_path(matches[0]["path"])
    def exchange(self,packet):
        # Only the restricted page writer above and bounded ROM reader below
        # can construct commands for this transport.
        if packet[0]!=0xaa or packet[1] not in (0x11,0x24):
            raise ValueError("Unexpected stock command")
        if packet[1]==0x24:
            at=WRITE_BASE+struct.unpack_from("<H",packet,3)[0]
            if packet!=write_frame(at,packet[8:8+packet[2]]):
                raise ValueError("Write packet failed the spare-page allowlist")
        for _ in range(16):
            if not self.dev.read(64,1):break
        if self.dev.write(b"\0"+packet)!=65:raise RuntimeError("Short HID write")
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            reply=bytes(self.dev.read(64,30))
            if len(reply)==65 and reply[0]==0:reply=reply[1:]
            if len(reply)==64 and reply[:8]==b"\x55"+packet[1:8]:return reply
        raise TimeoutError("No stock command response")
    def read_rom(self,address,length):
        if address<READ_BASE+8 or address+length>READ_BASE+0x10000 or length<=0:
            raise ValueError("Read outside the verified stock ROM window")
        result=bytearray()
        for at in range(address,address+length,48):
            count=min(48,address+length-at)
            packet=bytearray(64)
            packet[:3]=bytes((0xaa,0x11,count+8))
            struct.pack_into("<H",packet,3,at-8-READ_BASE)
            packet[5:8]=b"CHK"
            result.extend(self.exchange(bytes(packet))[16:16+count])
        return bytes(result)
    def close(self):self.dev.close()

def worker(args,stock,target,frames,plan):
    log={"started":datetime.now().isoformat(),"writes_requested":args.stage_extension,
         "probe_activated":False,"events":[]}
    args.journal.parent.mkdir(exist_ok=True,parents=True)
    def event(action,**details):
        item={"action":action,**details}
        log["events"].append(item)
        args.journal.write_text(json.dumps(log,indent=2),encoding="utf-8")
        print(json.dumps(item),flush=True)
    dev=None
    try:
        event("opening-stock-v118")
        dev=StockConfig()
        # Verify the complete command dispatcher, not only a version string.
        event("checking-dispatcher")
        code=dev.read_rom(0xeb60,0x764)
        if code!=stock[0xeb60:0xf2c4]:raise RuntimeError("Live dispatcher differs from pinned v1.18")
        for at in (HOOK_PAGE,PAGE):
            event("reading-page-twice",address=hex(at))
            first=dev.read_rom(at,PAGE_SIZE)
            second=dev.read_rom(at,PAGE_SIZE)
            if first!=second:raise RuntimeError(f"Live reads disagree for page {at:#x}")
            expected=stock[at:at+PAGE_SIZE]
            if at==PAGE and first==target:
                event("already-staged",sha256=digest(first))
                return
            if first!=expected:raise RuntimeError(f"Page {at:#x} changed; no write permitted")
            (args.journal.parent/f"page_{at:05x}_before.bin").write_bytes(first)
            event("page-backup-verified",address=hex(at),sha256=digest(first))
        event("preflight-pass",only_writable_page=hex(PAGE))
        if not args.stage_extension:return
        expected=bytearray(PAGE_SIZE)
        for i,packet in enumerate(frames):
            at=PAGE+i*48
            # Save the intent before touching the device, including the exact
            # protocol report, so interruption never hides an attempted write.
            event("write-inactive-page",index=i,address=hex(at),payload=packet.hex())
            dev.exchange(packet)  # Echo alone is NOT considered successful programming.
            expected[i*48:i*48+packet[2]]=packet[8:8+packet[2]]
            actual=dev.read_rom(PAGE,PAGE_SIZE)
            if actual!=expected:raise RuntimeError("Full page readback failed; stopped before any hook change")
            event("chunk-page-readback-pass",index=i,sha256=digest(actual))
        if dev.read_rom(PAGE,PAGE_SIZE)!=target:raise RuntimeError("Final page readback failed")
        if dev.read_rom(HOOK_PAGE,PAGE_SIZE)!=stock[HOOK_PAGE:HOOK_PAGE+PAGE_SIZE]:
            raise RuntimeError("Unexpected hook-page change")
        event("inactive-probe-staged-and-verified",sha256=digest(target),probe_activated=False)
    except Exception as e:
        event("error",message=str(e));raise
    finally:
        if dev is not None:dev.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument("--preflight",action="store_true",help="Only read and back up the two pages")
    modes.add_argument("--stage-extension",action="store_true",help="Program ONLY unused page 0x18000; do not activate it")
    p.add_argument("--journal",type=Path)
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=p.parse_args()
    stock,target,frames,plan=inputs()
    if not args.preflight and not args.stage_extension:
        out=BUILD/"usb_inactive_stage_plan.json"
        out.write_text(json.dumps(plan,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in plan.items() if k!="writes"},indent=2))
        return
    if args.journal is None:
        args.journal=ROOT/"backups"/("usb_preflight_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))/"journal.json"
    if args.worker:
        worker(args,stock,target,frames,plan);return
    command=[sys.executable,"-u",__file__,*sys.argv[1:],"--journal",str(args.journal),"--worker"]
    try:
        result=subprocess.run(command,timeout=55,capture_output=True,text=True,encoding="utf-8")
    except subprocess.TimeoutExpired:
        raise SystemExit(f"Native HID helper terminated after its deadline; see {args.journal}")
    print(result.stdout,end="");print(result.stderr,end="",file=sys.stderr)
    raise SystemExit(result.returncode)

if __name__=="__main__":main()
