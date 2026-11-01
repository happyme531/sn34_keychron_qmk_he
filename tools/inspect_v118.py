# /// script
# dependencies = ["pefile"]
# ///
"""Extract and compare official v1.18 resources without running its updater."""
from pathlib import Path
import hashlib
import json
import struct
import pefile

root=Path(__file__).resolve().parents[1]
source=root/"analysis/oem_updater_v118.exe"
pe=pefile.PE(str(source))
oldpe=pefile.PE(str(root/"analysis/oem_updater_v110.exe"))
for section in pe.sections:
    old=[s for s in oldpe.sections if s.Name==section.Name]
    if old:
        print("WRAPPER SECTION",section.Name.decode(errors="replace"),"same:",section.get_data()==old[0].get_data())
resources={}
for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if ty.id!=10:continue
    for item in ty.directory.entries:
        leaf=item.directory.entries[0].data.struct
        data=pe.get_data(leaf.OffsetToData,leaf.Size)
        resources[item.id]=data
        (root/f"analysis/v118_rcdata_{item.id}.bin").write_bytes(data)

stock=resources[4000]
live=(root/"analysis/live_v118_window_clean_a.bin").read_bytes()
other=(root/"analysis/live_v118_window_clean_b.bin").read_bytes()
assert live==other
def differences(start,end):
    mismatches=[a for a in range(start,end) if stock[a]!=live[a-0x9200]]
    runs=[]
    for a in mismatches:
        if runs and runs[-1][1]==a:
            runs[-1][1]=a+1
        else:runs.append([a,a+1])
    return {"start":hex(start),"end_exclusive":hex(end),"mismatch_count":len(mismatches),
            "difference_ranges":[[hex(a),hex(b)] for a,b in runs]}
result={"source":"https://www.eweadn.com/pages/driver-download", "wrapper_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "image_bytes":len(stock), "image_sha256":hashlib.sha256(stock).hexdigest(),
        "halfword_checksum":hex(sum(struct.unpack(f"<{len(stock)//2}H",stock))&0xffff),
        "resource_strings":{i:resources[i].decode("utf-16le",errors="replace") for i in (4008,4009,4010,4014,4016) if i in resources},
        "live_window_sha256":hashlib.sha256(live).hexdigest(),"live_alignment_reads_agree":True,
        "comparisons":[differences(0x9200,0xc000),differences(0xc000,0x19200)],
        "vectors":stock[:64].hex(),"tail":stock[-16:].hex(),"dispatcher_prefix":stock[0xeb60:0xeb80].hex()}
(root/"analysis/v118_comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
for at in (0x9800,0x14f60):
    print(hex(at),"file",stock[at:at+32].hex(),"live",live[at-0x9200:at-0x9200+32].hex())
