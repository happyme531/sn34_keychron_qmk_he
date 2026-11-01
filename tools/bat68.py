# /// script
# dependencies = ["hidapi"]
# ///
"""Configure the production BAT68 QMK platform (protocol 8). HE settings use
1/40 of estimated full travel; physical millimetres require calibration data.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import hid
from bat68_probe import Probe
from bat68_qmk import status
from bat68_model import load_board

ROOT=Path(__file__).resolve().parents[1]


class Raw:
    def __init__(self):
        usb=load_board()["usb"]
        devices=[d for d in hid.enumerate(int(usb["vid"],0),int(usb["pid"],0)) if d["usage_page"]==0xff60 and d["usage"]==0x61]
        if len(devices)!=1:raise RuntimeError(f"Expected one BAT68 QMK Raw HID interface, found {len(devices)}")
        self.device=hid.device();self.device.open_path(devices[0]["path"])
    def close(self):self.device.close()
    def query(self,data):
        if len(data)>32:raise ValueError("Raw HID request exceeds 32 bytes")
        data=bytes(data)+bytes(32-len(data))
        self.device.set_nonblocking(1)
        for _ in range(32):
            if not self.device.read(32):break
        self.device.set_nonblocking(0)
        if self.device.write(b"\0"+data)!=33:raise RuntimeError("Short raw HID write")
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            reply=bytes(self.device.read(32,50))
            if len(reply)==33 and reply[0]==0:reply=reply[1:]
            if len(reply)==32:
                if reply[0]==255:raise RuntimeError("Firmware rejected command: invalid range, unsupported operation, or held keys")
                if reply[0]==data[0]:return reply
        raise TimeoutError("BAT68 Raw HID response timed out")
    def he(self,cmd,payload=b""):
        reply=self.query(bytes((0xa9,cmd))+bytes(payload))
        if cmd in (0x11,0x13,0x14,0x15,0x16,0x1e,0x1f,0x40) and reply[2]:
            raise RuntimeError("Keychron HE handler rejected the configuration")
        return reply


def coordinates(key):
    mapping=load_board()["keys"]
    matches=[k for k in mapping if k["name"]==key or str(k["layout_index"])==key]
    if len(matches)!=1:raise ValueError("Choose a unique key name or layout index (Shift/Alt have duplicates)")
    return matches[0]["matrix"]


def numbers(value):
    values=[int(item,0) for item in value.split(",")]
    if len(values)!=4 or any(not 0<=v<=65535 for v in values):raise argparse.ArgumentTypeError("Expected four comma-separated 16-bit numbers")
    return values


def curve_points(value):
    try:points=[tuple(int(n,0) for n in pair.split(":")) for pair in value.split(",")]
    except ValueError as exc:raise argparse.ArgumentTypeError("Expected x:y,x:y,x:y,x:y") from exc
    if len(points)!=4 or any(len(p)!=2 or not 0<=p[0]<=40 or not 0<=p[1]<=127 for p in points):
        raise argparse.ArgumentTypeError("Four points required: x 0..40, y 0..127")
    if any(points[i][0]>=points[i+1][0] for i in range(3)):
        raise argparse.ArgumentTypeError("Curve x values must increase strictly")
    return bytes(n for p in points for n in p)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("status","get","set","select","he-set","toggle","clear-advanced","dks","socd","gamepad","controller","curve","calibrate","save"))
    p.add_argument("--points",type=curve_points,help="Gamepad curve, e.g. 0:0,10:31,30:95,40:127; omit to read")
    p.add_argument("--key");p.add_argument("--second-key")
    p.add_argument("--layer",type=int,choices=range(4),default=0)
    p.add_argument("--profile",type=int,choices=range(3))
    p.add_argument("--keycode",type=lambda v:int(v,0))
    p.add_argument("--mode",choices=("regular","rapid","neutral","last","first-key","second-key","deeper","deeper-single","off","hid","xinput"))
    p.add_argument("--actuation",type=int,choices=range(1,40),default=12,metavar="1..39")
    p.add_argument("--sensitivity",type=int,choices=range(1,40),default=4,metavar="1..39")
    p.add_argument("--release-sensitivity",type=int,choices=range(1,40),default=4,metavar="1..39")
    p.add_argument("--index",type=int,choices=range(20),default=0)
    p.add_argument("--shallow-act",type=int,default=10);p.add_argument("--shallow-release",type=int,default=8)
    p.add_argument("--deep-act",type=int,default=25);p.add_argument("--deep-release",type=int,default=22)
    p.add_argument("--keycodes",type=numbers,default=[5,6,0,0])
    p.add_argument("--actions",type=numbers,default=[0x0012,0x1200,0,0],help="Four packed DKS action words; nibble order: shallow press/release, deep press/release")
    p.add_argument("--axis",choices=("x-left","x-right","y-down","y-up","z-negative","z-positive","rx-negative","rx-positive","ry-down","ry-up","rz-negative","rz-positive"))
    p.add_argument("--button",type=int,choices=range(32));p.add_argument("--typing",action="store_true")
    p.add_argument("--action",choices=("status","start","finish"),default="status")
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    a=p.parse_args()
    requires_key=a.command in ("get","set","he-set","toggle","clear-advanced","dks","socd","gamepad")
    if requires_key and not a.key:p.error("--key is required ('all' is supported by he-set)")
    if a.key=="all" and a.command!="he-set":p.error("--key all is only supported by he-set")
    if a.command=="dks" and not (0<=a.shallow_release<a.shallow_act<a.deep_act<=40 and a.shallow_release<=a.deep_release<a.deep_act):
        p.error("DKS requires ordered shallow/deep press and release thresholds in 0..40")
    if a.command=="set" and (a.keycode is None or not 0<=a.keycode<=65535):p.error("set requires --keycode 0..65535")
    if a.command=="select" and a.profile is None:p.error("select requires --profile")
    if not a.worker:raise SystemExit(subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=30).returncode)
    probe=Probe();raw=None
    try:
        info=status(probe)
        if info["protocol"]!=8:raise RuntimeError("Production protocol-8 firmware is not installed; no configuration written")
        raw=Raw();profiles=raw.he(0x10);profile=profiles[2] if a.profile is None else a.profile
        r,c=coordinates(a.key) if requires_key and a.key!="all" else (0,0)
        if a.command=="get":
            reply=raw.query((4,a.layer,r,c));print(json.dumps(dict(key=a.key,layer=a.layer,keycode=f"0x{int.from_bytes(reply[4:6],'big'):04X}"),indent=2));return
        if a.command=="set":raw.query((5,a.layer,r,c,a.keycode>>8,a.keycode&255))
        elif a.command=="select":raw.he(0x11,(profile,))
        elif a.command=="he-set":
            if a.mode not in ("regular","rapid"):p.error("he-set requires --mode regular or rapid")
            mask=bytearray(18)
            if a.key!="all":mask[r*3:r*3+3]=(1<<c).to_bytes(3,"little")
            raw.he(0x14,bytes((profile,1 if a.mode=="regular" else 2,a.actuation,a.sensitivity,a.release_sensitivity,a.key=="all"))+mask)
            raw.he(0x1f,(profile,))
        elif a.command in ("toggle","clear-advanced","gamepad","dks"):
            mode={"clear-advanced":0,"dks":1,"gamepad":2,"toggle":3}[a.command];index=a.index;extra=b""
            if a.command=="gamepad":
                axes=("x-left","x-right","y-down","y-up","z-negative","z-positive","rx-negative","rx-positive","ry-down","ry-up","rz-negative","rz-positive")
                if (a.axis is None)==(a.button is None):p.error("gamepad requires exactly one of --axis or --button")
                index=13+a.button if a.button is not None else axes.index(a.axis)
            if a.command=="dks":extra=bytes((a.shallow_act,a.shallow_release,a.deep_act,a.deep_release))+struct.pack("<4H",*a.keycodes)+struct.pack("<4H",*a.actions)
            raw.he(0x15,bytes((profile,mode,r,c,index))+extra);raw.he(0x1f,(profile,))
        elif a.command=="socd":
            modes={"off":0,"deeper":1,"deeper-single":2,"last":3,"first-key":4,"second-key":5,"neutral":6}
            if a.mode not in modes or not a.second_key:p.error("socd requires --second-key and a SOCD --mode")
            r2,c2=coordinates(a.second_key);raw.he(0x16,(profile,r,c,r2,c2,a.index,modes[a.mode]));raw.he(0x1f,(profile,))
        elif a.command=="controller":
            if a.mode not in ("hid","xinput"):p.error("controller requires --mode hid or xinput")
            raw.he(0x23,((a.mode=="xinput")|(a.typing<<1),))
        elif a.command=="curve" and a.points is not None:raw.he(0x21,a.points)
        elif a.command=="calibrate" and a.action!="status":raw.he(0x40,(2 if a.action=="start" else 4,))
        elif a.command=="save":probe.query(0x79,payload=b"SAVE")
        profiles=raw.he(0x10);cal=raw.he(0x41);gc=raw.he(0x22);curve=raw.he(0x20)
        print(json.dumps(dict(status=status(probe),active_profile=profiles[2],profile_count=profiles[3],
            calibration_phase=cal[3],calibration_flags=cal[2],controller_mode="xinput" if gc[3]&1 else "hid",
            typing_with_gamepad=bool(gc[3]&2),save="Changes persist automatically after an idle debounce; save explicitly flushes cached settings",
            gamepad_curve=[list(curve[i:i+2]) for i in range(2,10,2)],
            travel_unit="1/40 of estimated full travel, not measured millimetres"),indent=2))
    finally:
        if raw:raw.close()
        probe.close()


if __name__=="__main__":main()
