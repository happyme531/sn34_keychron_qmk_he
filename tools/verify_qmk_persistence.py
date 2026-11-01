# /// script
# dependencies = ["hidapi"]
# ///
"""Verify saved keymaps on hardware using an unconnected matrix position."""
import hashlib
import argparse
import json
from pathlib import Path
import struct
import time
import zlib
from bat68_probe import Probe
from bat68_qmk import restart,save,status

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"analysis/qmk_v2_hardware_verification.json"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation",choices=("v2","v3"),default="v2")
    args=parser.parse_args()
    output=ROOT/f"analysis/qmk_{args.generation}_hardware_verification.json"
    mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
    assert not any(k["raw_slot"]==0 for k in mapping)
    report={"status":"IN_PROGRESS","checks":[],"uses_unconnected_position":True}
    def checked(name,**values):
        report["checks"].append({"check":name,**values})
        output.write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report["checks"][-1]),flush=True)
    probe=Probe()
    try:
        before=status(probe)
        assert before["protocol"]>=2 and before["keyboard_mode"]=="qmk"
        assert before["default_keyboard_mode"]=="qmk"
        if args.generation=="v3":assert before["protocol"]>=3 and before["open_flash_driver"]
        deadline=time.monotonic()+10
        while any(status(probe)["matrix"]):
            if time.monotonic()>deadline:raise RuntimeError("Release all keys before the save/restart test")
            time.sleep(0.1)
        old=struct.unpack_from("<H",probe.query(0x76,0,0),8)[0]
        assert old==0,"Unexpected keycode on unconnected position"
        checked("QMK active immediately after OTA",status=before)

        initial=save(probe)
        checked("Initial keymap saved",result=initial)
        base_sequence=initial["saved_sequence"]
        skip=save(probe)
        assert not skip["flash_written"] and skip["saved_sequence"]==base_sequence
        checked("Unchanged keymap skips Flash write",result=skip)

        probe.query(0x75,0,0,4)
        assert status(probe)["unsaved_changes"]
        changed=save(probe)
        assert changed["flash_written"] and changed["saved_sequence"]==(base_sequence+1)&0xffffffff
        checked("Changed unconnected position saved to other page",result=changed)
        probe,after=restart(probe)
        assert after["keyboard_mode"]=="qmk" and not after["unsaved_changes"]
        assert after["saved_sequence"]==changed["saved_sequence"]
        assert struct.unpack_from("<H",probe.query(0x76,0,0),8)[0]==4
        checked("Restart reloads saved change and QMK mode",status=after)

        probe.query(0x75,0,0,old)
        restored=save(probe)
        assert restored["flash_written"] and restored["saved_sequence"]==(base_sequence+2)&0xffffffff
        probe,after=restart(probe)
        assert struct.unpack_from("<H",probe.query(0x76,0,0),8)[0]==old
        assert after["keyboard_mode"]=="qmk" and not after["unsaved_changes"]
        assert after["saved_sequence"]==restored["saved_sequence"]
        checked("Original keymap restored, saved and reloaded",status=after)

        records=[]
        backup=ROOT/f"backups/usb_qmk_{args.generation}_20261030"
        backup.mkdir(parents=True,exist_ok=True)
        for slot,address in enumerate((0x7d000,0x7d200)):
            data=bytearray()
            for at in range(0,512,48):
                count=min(48,512-at)
                reply=probe.query(0x73,count,address+at)
                assert reply[2]==count and struct.unpack_from("<I",reply,56)[0]==address+at
                data.extend(reply[8:8+count])
            magic,version,size,sequence,reserved=struct.unpack_from("<IHHII",data)
            crc,commit=struct.unpack_from("<II",data,400)
            assert magic==0x4b383642 and version==1 and size==512 and reserved==0
            assert crc==zlib.crc32(data[:400]) and commit==0xc0deb68a
            (backup/f"settings_slot_{slot}.bin").write_bytes(data)
            records.append({"slot":slot,"address":hex(address),"sequence":sequence,
                            "sha256":hashlib.sha256(data).hexdigest(),"crc32_valid":True})
        checked("Both physical settings pages read back with valid CRC",records=records)
        report.update(status="HARDWARE_PERSISTENCE_AND_RESTART_VERIFIED",final_status=status(probe),
                      physical_keys_changed=False,original_keymap_restored=True,
                      typing_and_fn_evidence="analysis/qmk_v1_hardware_verification.json",
                      limits=["Reboot was tested; manual USB unplug/replug was not repeated for v2",
                              "Power-loss recovery was emulated, not fault-injected on hardware"])
        report["flash_backend"]="SONiX SDK v2.1.4 HAL" if before.get("open_flash_driver") else "original firmware"
        output.write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps({"status":report["status"],"output":str(output)}),flush=True)
    except Exception as exc:
        report.update(status="FAILED",error=repr(exc))
        output.write_text(json.dumps(report,indent=2),encoding="utf-8")
        raise
    finally:probe.close()

if __name__=="__main__":main()
