# /// script
# dependencies = ["hidapi"]
# ///
"""Configure BAT68 Keychron HE. Travel settings are fractions of estimated full
stroke (1/40), NOT measured millimetres. Changes are staged until explicit save.
"""
import argparse
import json
import subprocess
import sys
from bat68_probe import Probe
from bat68_qmk import status, MAPPING


def query(probe, op, profile=0, row=0, col=0, mode=1, actuation=12, sensitivity=4, release_sensitivity=4):
    return probe.query(0x7c,payload=bytes((op,profile,row,col,mode,actuation,sensitivity,release_sensitivity)))


def he_status(probe):
    r=query(probe,0)
    return dict(version=r[8],profile=r[9],profile_count=r[10],unsaved_changes=bool(r[11]),
                global_mode={1:"regular",2:"rapid"}.get(r[12],r[12]),actuation=r[13],
                sensitivity=r[14],release_sensitivity=r[15],saved_sequence=int.from_bytes(r[16:20],"little"),
                setting_unit="1/40 of estimated full stroke; not measured millimetres")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("status","select","get","set","save","reset"))
    parser.add_argument("--profile",type=int,choices=range(3))
    parser.add_argument("--key",help="Key name, layout index, or 'all' to set global defaults")
    parser.add_argument("--mode",choices=("regular","rapid"))
    parser.add_argument("--actuation",type=int,choices=range(1,40),default=12,metavar="1..39")
    parser.add_argument("--sensitivity",type=int,choices=range(1,40),default=4,metavar="1..39")
    parser.add_argument("--release-sensitivity",type=int,choices=range(1,40),default=4,metavar="1..39")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.command in ("select","reset") and args.profile is None: parser.error("--profile is required")
    row=col=0
    if args.command in ("get","set"):
        if args.key=="all" and args.command=="set": row=col=255
        else:
            matches=[key for key in MAPPING if key["name"]==args.key or str(key["layout_index"])==args.key]
            if len(matches)!=1: parser.error("--key must name one mapped key (use layout index for duplicate Shift/Alt)")
            row,col=divmod(matches[0]["raw_slot"],16)
    if args.command=="set" and not args.mode: parser.error("set requires --mode regular or rapid")
    if not args.worker:
        raise SystemExit(subprocess.run([sys.executable,"-u",__file__,*sys.argv[1:],"--worker"],timeout=25).returncode)
    probe=Probe()
    try:
        if status(probe)["protocol"]!=7: raise RuntimeError("This helper requires protocol 7; production protocol 8 uses tools/bat68.py")
        before=he_status(probe)
        profile=before["profile"] if args.profile is None else args.profile
        op={"status":0,"select":1,"set":2,"save":3,"get":4,"reset":5}[args.command]
        if args.command=="get" and profile!=before["profile"]: raise RuntimeError("get reads the active profile; select it first")
        r=query(probe,op,profile,row,col,2 if args.mode=="rapid" else 1,args.actuation,args.sensitivity,args.release_sensitivity)
        result=he_status(probe)
        if args.command=="get": result.update(key=args.key,travel=r[8],travel_full_scale=240,mode=r[9],pressed=bool(r[10]))
        print(json.dumps(result,indent=2))
    finally: probe.close()


if __name__=="__main__": main()
