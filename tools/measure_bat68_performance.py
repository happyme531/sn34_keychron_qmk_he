# /// script
# dependencies = ["hidapi"]
# ///
"""Read real-board timing and raw noise; optional volatile scan comparison mode."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import struct
import time
from bat68_probe import Probe
from bat68_qmk import performance_status, status, usb_status

FIELDS=("adc_cycles","adc_calls","adc_max_cycles","usb_cycles","he_cycles","he_max_cycles",
        "key_cycles","key_max_cycles","pre_cycles","post_cycles","clock_hz","cycles","millis")

def timing(probe):
    packet=probe.query(0x7f)
    assert packet[2]==56 and packet[8]==1
    return dict(mode=packet[9],**dict(zip(FIELDS,struct.unpack_from("<13I",packet,12))))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds",type=float,default=3)
    parser.add_argument("--samples",type=int,default=100)
    parser.add_argument("--mode",type=int,choices=(0,1,3,7))
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    probe=Probe()
    try:
        if args.mode is not None:
            assert args.mode==0 or not any(status(probe)["matrix"]),"Release keys before changing scan timing"
            probe.query(0x7f,2,payload=struct.pack("<I",args.mode));time.sleep(.05)
        try:
            registers=list(struct.unpack_from("<13I",probe.query(0x7f,1),12))
            first_t=timing(probe)
        except RuntimeError:
            if args.mode is not None:raise
            registers=None;first_t=None
        first=performance_status(probe);started=time.perf_counter()
        time.sleep(args.seconds)
        last=performance_status(probe);elapsed=time.perf_counter()-started
        last_t=timing(probe) if first_t else None
        delta={k:(last[k]-first[k])&0xffffffff for k in
               ("adc_frames","he_frames","skipped_frames","main_loops","gated_loops","flash_pages","flash_commits")}
        result=dict(timestamp=datetime.now().astimezone().isoformat(),seconds=elapsed,
                    rates={k+"_hz":delta[k]/elapsed for k in ("adc_frames","he_frames","main_loops")},
                    delta=delta,status=status(probe),usb=usb_status(probe),adc_registers=registers,
                    first=first,last=last,first_timing=first_t,last_timing=last_t)
        if first_t:
            td={k:(last_t[k]-first_t[k])&0xffffffff for k in FIELDS}
            seconds=td["millis"]/1000
            cycles=seconds*last_t["clock_hz"]
            result["cpu"]=dict(mode=last_t["mode"],seconds=seconds,
                adc_irq_percent=td["adc_cycles"]*100/cycles,usb_irq_percent=td["usb_cycles"]*100/cycles,
                he_percent=td["he_cycles"]*100/cycles,key_percent=td["key_cycles"]*100/cycles,
                pre_percent=td["pre_cycles"]*100/cycles,post_percent=td["post_cycles"]*100/cycles,
                mean_he_us=td["he_cycles"]*1e6/last_t["clock_hz"]/max(1,delta["he_frames"]),
                mean_key_us=td["key_cycles"]*1e6/last_t["clock_hz"]/max(1,delta["main_loops"]),
                mean_adc_irq_us=td["adc_cycles"]*1e6/last_t["clock_hz"]/max(1,td["adc_calls"]),
                max_he_us=last_t["he_max_cycles"]*1e6/last_t["clock_hz"],
                max_key_us=last_t["key_max_cycles"]*1e6/last_t["clock_hz"])
        samples=[]
        for _ in range(args.samples):
            raw=[]
            for at in range(0,96,24):raw.extend(struct.unpack_from("<24H",probe.query(0x71,24,at),8))
            samples.append(raw)
        if samples:
            result["raw_noise"]=[dict(slot=i,mean=statistics.mean(v),stdev=statistics.pstdev(v),
                minimum=min(v),maximum=max(v),p05=sorted(v)[len(v)//20],p95=sorted(v)[len(v)*19//20])
                for i,v in enumerate(zip(*samples))]
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in result.items() if k in ("rates","cpu","delta","timestamp")},indent=2))
        print("Saved",args.output)
    finally:probe.close()

if __name__=="__main__":main()
