"""Decode the bounded RAM snapshot and the SDK ADC register fields."""
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
snapshot=json.loads((ROOT/"analysis/hw_snapshot_v4_idle.json").read_text())["registers"]
values={item["name"]:int(item["value"],0) for item in snapshot}
raw=json.loads((ROOT/"analysis/raw_v4_idle.json").read_text())
mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]

def u16(label,index):return (values[f"{label}.pair{index//2}"]>>(16*(index%2)))&65535
keys=[]
for key in mapping:
    e=key["electrical"]
    keys.append({"name":key["name"],"electrical":e,"raw_slot":key["raw_slot"],"raw":raw[key["raw_slot"]],
                 **{label:u16(label,e) for label in ("idle","pressed","current_raw","previous_raw","travel")}})
svd=ET.parse(ROOT/"analysis/sdk/SONiX.SN34F2_DFP.2.0.4/SVD/SN34F280.svd")
adc=next(p for p in svd.findall(".//peripherals/peripheral") if p.findtext("name")=="SN_ADC0")
registers={}
for r in adc.findall("registers/register"):
    name=r.findtext("name")
    if f"SN_ADC0.{name}" not in values or name.startswith("DATA"):continue
    value=values[f"SN_ADC0.{name}"]
    fields={}
    for f in r.findall("fields/field"):
        if f.findtext("bitOffset") is not None:
            low=int(f.findtext("bitOffset"));width=int(f.findtext("bitWidth"))
        elif f.findtext("bitRange") is not None:
            high,low=map(int,re.findall(r"\d+",f.findtext("bitRange")));width=high-low+1
        else:continue
        fields[f.findtext("name")]=(value>>low)&((1<<width)-1)
    registers[name]={"value":hex(value),"fields":fields}
result={"keys":keys,"adc_registers":registers,
        "v118_mux_pins":["P2.9 = phase bit 0","P0.0 = phase bit 1","P0.1 = phase bit 2"],
        "gating_pin":"P1.12",
        "note":"Physical mux pins decoded from v1.18 function 0x450c; old v1.10 notes are not authoritative for this image"}
(ROOT/"analysis/hall_board_profile.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps({"example_keys":keys[:8],"adc_registers":registers},indent=2))
