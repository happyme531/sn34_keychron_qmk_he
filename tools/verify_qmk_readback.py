"""Verify the hardware ROM dump matches the built image plus saved settings."""
import hashlib
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/"backups/usb_qmk_v2_20261030"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation",choices=("v2","v3"),default="v2")
    args=parser.parse_args()
    backup=ROOT/f"backups/usb_qmk_{args.generation}_20261030"
    expected=bytearray((ROOT/"build/qmk_bridge/bat68_qmk_bridge_v118.bin").read_bytes())
    pristine_sha=hashlib.sha256(expected).hexdigest()
    for slot,address in enumerate((0x7d000,0x7d200)):
        page=(backup/f"settings_slot_{slot}.bin").read_bytes()
        assert len(page)==512
        expected[address:address+512]=page
    actual=(backup/f"app_qmk_{args.generation}_saved_504k.bin").read_bytes()
    if actual!=expected:
        differences=[i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b]
        raise AssertionError(f"Unexpected application differences: length={len(actual)}, first={differences[:32]}")
    original_boot=(ROOT/"backups/usb_20261029/boot_00200000_8k.bin").read_bytes()
    current_boot=(backup/"boot_00200000_8k.bin").read_bytes()
    assert current_boot==original_boot,"Boot changed"
    report={"status":"FULL_HARDWARE_READBACK_VERIFIED","bytes":len(actual),
            "built_image_sha256":pristine_sha,"live_image_sha256":hashlib.sha256(actual).hexdigest(),
            "only_changes_from_built_image":"The two verified 512-byte keymap settings pages",
            "boot_unchanged":True,"boot_sha256":hashlib.sha256(current_boot).hexdigest()}
    output=ROOT/f"analysis/qmk_{args.generation}_full_readback_verification.json"
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    manifest_path=ROOT/"build/qmk_bridge/manifest.json"
    manifest=json.loads(manifest_path.read_text())
    assert manifest["image_sha256"]==pristine_sha
    manifest.update(status="HARDWARE_VERIFIED_QMK_PERSISTENCE",hardware_verification=[
        "analysis/qmk_v1_hardware_verification.json",
        f"analysis/qmk_{args.generation}_hardware_verification.json",
        f"analysis/qmk_{args.generation}_full_readback_verification.json",
        f"analysis/qmk_{args.generation}_ota_result.json"])
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
