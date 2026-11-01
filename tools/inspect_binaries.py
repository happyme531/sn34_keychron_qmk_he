"""Read-only PE/firmware inspection; run with uv run --with pefile."""
from pathlib import Path
import hashlib
import json
import re
import struct

import pefile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
OUT.mkdir(exist_ok=True)
summary = []
paths = list(ROOT.glob("*.exe")) + list(OUT.glob("*/DeviceDriver.exe"))
for index, path in enumerate(paths):
    data = path.read_bytes()
    pe = pefile.PE(data=data)
    tag = f"binary_{index}"
    strings = [(m.start(), m.group().decode("ascii")) for m in re.finditer(rb"[\x20-\x7e]{5,}", data)]
    strings += [(m.start(), m.group().decode("utf-16le")) for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", data)]
    (OUT / f"{tag}_strings.txt").write_text("\n".join(f"{off:08x} {s}" for off, s in sorted(strings)), encoding="utf-8")
    resources = []
    def walk(directory, parts=()):
        for item in directory.entries:
            name = str(item.name) if item.name else str(item.id)
            if hasattr(item, "directory"):
                walk(item.directory, parts + (name,))
            elif parts and parts[0] == "10":
                blob = pe.get_data(item.data.struct.OffsetToData, item.data.struct.Size)
                dest = OUT / f"{tag}_rcdata_{'_'.join(parts[1:] + (name,))}.bin"
                dest.write_bytes(blob)
                resources.append({"name": dest.name, "size": len(blob), "head": blob[:64].hex(), "tail": blob[-64:].hex()})
    if hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        walk(pe.DIRECTORY_ENTRY_RESOURCE)
    summary.append({"file": str(path.relative_to(ROOT)), "tag": tag, "sha256": hashlib.sha256(data).hexdigest(), "machine": hex(pe.FILE_HEADER.Machine), "resources": resources})
(OUT / "pe_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
