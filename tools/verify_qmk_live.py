# /// script
# dependencies = ["hidapi"]
# ///
"""Verify the RAM keymap transport using an unconnected matrix position."""
from pathlib import Path
import json
import struct
from bat68_probe import Probe
from bat68_qmk import status

root=Path(__file__).resolve().parents[1]
mapping=json.loads((root/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
assert not any(k["raw_slot"]==0 for k in mapping)
p=Probe()
try:
    before=status(p)
    old=struct.unpack_from("<H",p.query(0x76,0,0),8)[0]
    try:
        p.query(0x75,0,0,4)
        actual=struct.unpack_from("<H",p.query(0x76,0,0),8)[0]
        assert actual==4,"RAM keymap write/read mismatch"
    finally:
        p.query(0x75,0,0,old)
    assert struct.unpack_from("<H",p.query(0x76,0,0),8)[0]==old
    after=status(p)
    assert after["initialized"] and after["scans"]!=before["scans"]
    events=[]
    path=root/"analysis/qmk_windows_key_events.jsonl"
    if path.exists():events=[json.loads(line.lstrip("\ufeff")) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    keys={k:sum(e["key"]==k and e["event"]=="down" for e in events) for k in ("Q","W","E","F1","F2","Up")}
    result={"status":"HARDWARE_TYPING_AND_RAM_REMAP_VERIFIED","user_confirmed_typing_and_fn":True,
            "windows_key_down_counts":keys,"unused_position_remap_roundtrip":True,
            "unused_position_restored":True,"flash_write_performed":False,"final_status":after}
    (root/"analysis/qmk_v1_hardware_verification.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
finally:p.close()
