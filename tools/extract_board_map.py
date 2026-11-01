"""Read the v1.18 electrical/layout lookup from the pinned, running image."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
data=(root/"analysis/v118_rcdata_4000.bin").read_bytes()
assert hashlib.sha256(data).hexdigest()=="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36"
text=(root/"analysis/calibration/keyboard.xml").read_text(encoding="utf-8")
xml=ET.fromstring(re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;',text))
layout={int(k.attrib["key_index"]):k.attrib for k in xml.findall(".//key")}
keys=[]
for electrical,index in enumerate(data[0x14fe4:0x15064]):
    if index==0x7d:continue
    group,slot=electrical&7,electrical>>3
    assert group<6
    name=layout.get(index,{}).get("name","UNKNOWN")
    keys.append({"electrical":electrical,"layout_index":index,"name":name,
                 "hid_usage":layout.get(index,{}).get("code"),"raw_slot":group*16+slot,
                 "row_col":layout.get(index,{}).get("row_col"),
                 "rect":[int(layout.get(index,{}).get("rect_"+p,0)) for p in ("left","top","width","height")]})
missing=[{"layout_index":index,"name":v["name"]} for index,v in layout.items() if not any(k["layout_index"]==index for k in keys)]
result={"stock_version":"1.18","mapping_source":"0x14fe4..0x15063",
        "raw_slots":96,"adc_snapshot_ram":"0x200039f8","keys":keys,
        "active_keys":len(keys),"layout_keys":len(layout),"unmapped_layout_keys":missing}
(root/"analysis/board_map_v118.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="keys"},ensure_ascii=False,indent=2))
print(json.dumps([k for k in keys if k["name"] in ("W","A","S","D","Esc","Fn","Space")],ensure_ascii=False,indent=2))
