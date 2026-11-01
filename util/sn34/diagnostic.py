# /// script
# dependencies = ["hidapi"]
# ///
"""Control the QMK bridge. set changes RAM; save persists it across restarts."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
from transport import Probe
from model import load_board

ROOT=Path(__file__).resolve().parents[2]
MAPPING=load_board()["keys"]
def status(probe):
    r=probe.query(0x74)
    if r[8:12]!=load_board()["usb"]["diagnostic_tag"].encode("ascii")+b"Q":raise RuntimeError("Compatible QMK diagnostic firmware is not installed")
    info={"qmk":True,"protocol":r[12],"layers":r[13],"rows":r[14],"columns":r[15],
            "layer_state":r[16],"initialized":bool(r[17]),"report_pending":bool(r[18]),
            "keyboard_mode":"qmk" if r[19] else "stock",
            "actuation":struct.unpack_from("<H",r,20)[0],"release":struct.unpack_from("<H",r,22)[0],
            "matrix":list(struct.unpack_from("<6H",r,24)),"scans":struct.unpack_from("<I",r,36)[0],
            "qmk_report":list(r[40:48])}
    if r[12]>=2:
        info.update(saved_sequence=struct.unpack_from("<I",r,48)[0],
                    saved_slot=None if r[52]==255 else r[52],unsaved_changes=bool(r[53]),
                    default_keyboard_mode="qmk" if r[54] else "stock",settings_format=r[55])
    if r[12]>=3:
        flags,words=struct.unpack_from("<HH",r,56)
        info.update(open_flash_driver=bool(flags&1),hardware_snapshot=bool(flags&2),snapshot_words=words,
                    native_usb_trial_available=bool(flags&4),native_usb_trial_bytes=struct.unpack_from("<H",r,60)[0],
                    source_adc_driver=bool(flags&8),source_usb_stack=bool(flags&16),
                    bringup_guard=bool(flags&32),standalone_application=bool(flags&64))
        info["keychron_he"]=bool(flags&128)
        if info["keychron_he"]:
            info.update(actuation=None,release=None,hall_thresholds="Per-key Keychron HE settings; use util/sn34/bat68.py")
    if r[12]>=8:
        info.pop("qmk_report",None)
        info.update(report_overflows=struct.unpack_from("<I",r,60)[0],matrix_coordinates="Logical QMK coordinates from the selected keyboard model")
    return info

def save(probe):
    if status(probe)["protocol"]<2:raise RuntimeError("Persistent keymaps require QMK bridge protocol 2")
    r=probe.query(0x79,payload=b"SAVE")
    return {"flash_written":bool(r[8]),"saved_slot":r[9],
            "saved_sequence":struct.unpack_from("<I",r,12)[0],"status":status(probe)}


def usb_status(probe):
    r=probe.query(0x7b)
    if r[2]!=24 or r[8]!=1:raise RuntimeError("USB diagnostics require the v26 firmware")
    reads,irqs,elapsed,detached=struct.unpack_from("<4I",r,16)
    return dict(schema=r[8],device_state=r[9],speed={0:"high",1:"full"}.get(r[10],str(r[10])),
                recovery_phase={0:"normal",1:"detached",2:"full_speed_retry",3:"failed"}.get(r[11],str(r[11])),
                configured_once=bool(r[12]),error=struct.unpack_from("b",r,13)[0],
                device_descriptor_reads=reads,usb_irqs=irqs,elapsed_ms=elapsed,detached_at_ms=detached)


def performance_status(probe):
    r=probe.query(0x7d)
    if r[2]!=56 or r[8]!=1:raise RuntimeError("Performance diagnostics require v27")
    fields=("adc_frames","he_frames","skipped_frames","main_loops","gated_loops","queue_peak",
            "axis_coalesced","flash_pages","flash_commits","max_flash_page_ms","max_loop_gap_cycles","queued","clock_hz")
    info=dict(zip(fields,struct.unpack_from("<13I",r,12)))
    info.update(unsaved_changes=bool(r[9]),max_loop_gap_us=info["max_loop_gap_cycles"]*1e6/info["clock_hz"])
    return info

def restart(probe):
    if status(probe)["protocol"]<2:raise RuntimeError("Restart requires QMK bridge protocol 2")
    probe.query(0x7a,payload=b"REBT")
    probe.close()
    time.sleep(0.75)
    deadline=time.monotonic()+10
    last_error=None
    while time.monotonic()<deadline:
        candidate=None
        try:
            candidate=Probe()
            info=status(candidate)
            return candidate,info
        except (OSError,RuntimeError,TimeoutError) as exc:
            last_error=exc
            if candidate:candidate.close()
            time.sleep(0.2)
    raise TimeoutError(f"Keyboard did not return after restart: {last_error}")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("status","usb","perf","enable","disable","get","set","save","reboot","travel","hardware","record"))
    p.add_argument("--key",help="Key name, or numeric layout index for duplicate names")
    p.add_argument("--layer",type=int,choices=(0,1),default=0)
    p.add_argument("--keycode",type=lambda x:int(x,0))
    p.add_argument("--seconds",type=float,default=10)
    p.add_argument("--output",type=Path)
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=p.parse_args()
    if not args.worker:
        try:r=subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=max(20,args.seconds+10))
        except subprocess.TimeoutExpired:raise SystemExit("USB QMK helper timed out and was terminated")
        raise SystemExit(r.returncode)
    probe=Probe()
    try:
        info=status(probe)
        if args.command=="usb":info=usb_status(probe)
        if args.command=="perf":
            started=time.perf_counter();first=performance_status(probe);time.sleep(args.seconds)
            info=performance_status(probe);elapsed=time.perf_counter()-started
            for name in ("adc_frames","he_frames","main_loops"):
                info[name+"_hz"]=((info[name]-first[name])&0xffffffff)/elapsed
        if args.command in ("enable","disable"):
            if args.command=="disable" and info.get("standalone_application"):
                raise RuntimeError("Standalone firmware always uses QMK; the original application has been removed")
            probe.query(0x78,int(args.command=="enable"));time.sleep(0.02);info=status(probe)
        elif args.command in ("get","set"):
            if info["protocol"]>=8:raise RuntimeError("Use util/sn34/bat68.py for production matrix coordinates and four layers")
            matches=[k for k in MAPPING if k["name"]==args.key]
            if not matches:matches=[k for k in MAPPING if str(k["layout_index"])==args.key]
            if len(matches)!=1:p.error("Choose an unambiguous key name or layout index")
            key=matches[0];row,col=divmod(key["raw_slot"],16)
            if args.command=="set" and (args.keycode is None or not 0<=args.keycode<=65535):p.error("set needs --keycode 0..65535")
            r=probe.query(0x75 if args.command=="set" else 0x76,args.layer,row|(col<<8),args.keycode or 0)
            info={"key":key["name"],"layout_index":key["layout_index"],"layer":args.layer,
                  "keycode":f"0x{struct.unpack_from('<H',r,8)[0]:04X}",
                  "storage":"RAM; run save to keep changes across restarts" if info["protocol"]>=2 else "RAM; power cycle restores compiled keymap"}
        elif args.command=="save":info=save(probe)
        elif args.command=="reboot":probe,info=restart(probe)
        elif args.command=="hardware":
            from hardware_registers import REGISTERS
            if not info.get("hardware_snapshot"):raise RuntimeError("Hardware snapshot requires QMK bridge protocol 3")
            if info["snapshot_words"]!=len(REGISTERS):raise RuntimeError("Hardware snapshot register list differs from the installed firmware")
            words=[]
            for at in range(0,len(REGISTERS),12):
                count=min(12,len(REGISTERS)-at)
                r=probe.query(0x7b,count,at)
                if r[2]!=count*4 or struct.unpack_from("<H",r,3)[0]!=at:raise RuntimeError("Malformed hardware snapshot")
                words.extend(struct.unpack_from(f"<{count}I",r,8))
            info={"registers":[{**item,"address":hex(item["address"]),"value":hex(value)} for item,value in zip(REGISTERS,words)]}
        elif args.command=="travel":
            values=[]
            for at in range(0,128,24):
                count=min(24,128-at);r=probe.query(0x77,count,at)
                values.extend(struct.unpack_from(f"<{count}H",r,8))
            info={k["name"]+"_"+str(k["layout_index"]):values[k["electrical"]] for k in MAPPING}
        elif args.command=="record":
            if not args.output or not 0<args.seconds<=600:p.error("record needs --output and 0<seconds<=600")
            args.output.parent.mkdir(exist_ok=True,parents=True)
            start=time.monotonic();n=0
            with args.output.open("w",encoding="utf-8",buffering=1) as f:
                while time.monotonic()-start<args.seconds:
                    item={"t":time.monotonic()-start,**status(probe)}
                    f.write(json.dumps(item)+"\n");n+=1
                    time.sleep(0.005)
            info={"frames":n,"output":str(args.output),"final_status":status(probe)}
        print(json.dumps(info,ensure_ascii=False,indent=2),flush=True)
        if args.output and args.command!="record":
            args.output.parent.mkdir(exist_ok=True,parents=True)
            args.output.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:probe.close()

if __name__=="__main__":main()
