# /// script
# dependencies = ["hidapi"]
# ///
"""Measure input processing under several RGB effects, restoring the active effect."""
import argparse
import json
from pathlib import Path
import time
from bat68 import Raw
from bat68_probe import Probe
from bat68_qmk import performance_status,status,usb_status

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds",type=float,default=3)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    mapping=json.loads(Path("build/bat68/rgb_protocol.json").read_text())
    wanted=("SOLID_COLOR","CYCLE_SPIRAL","DIGITAL_RAIN","TYPING_HEATMAP","SOLID_MULTISPLASH")
    effects=[entry for name in wanted for entry in mapping if entry["name"]==name]
    raw=Raw();probe=Probe();original=None;before=None;results=[]
    try:
        original=raw.query(bytes((8,3,2)))[3]
        before=status(probe)
        for effect in effects:
            assert raw.query(bytes((7,3,2,effect["wire"])))[3]==effect["wire"]
            time.sleep(.15)
            first=performance_status(probe);started=time.perf_counter()
            time.sleep(args.seconds)
            last=performance_status(probe);seconds=time.perf_counter()-started
            delta={k:(last[k]-first[k])&0xffffffff for k in
                   ("adc_frames","he_frames","skipped_frames","main_loops","gated_loops","flash_pages")}
            result=dict(effect=effect["name"],seconds=seconds,delta=delta,
                        rates={k+"_hz":delta[k]/seconds for k in ("adc_frames","he_frames","main_loops")},
                        report_overflows=status(probe)["report_overflows"])
            results.append(result);print(json.dumps(result),flush=True)
    finally:
        try:
            if original is not None:
                raw.query(bytes((7,3,2,original)))
                restored=raw.query(bytes((8,3,2)))[3]
                assert restored==original,"Original RGB effect was not restored"
            final=dict(original_effect_wire=original,restored_effect_wire=original,before=before,
                       after=status(probe),usb=usb_status(probe),results=results)
            args.output.write_text(json.dumps(final,indent=2),encoding="utf-8")
        finally:
            probe.close();raw.close()

if __name__=="__main__":main()
