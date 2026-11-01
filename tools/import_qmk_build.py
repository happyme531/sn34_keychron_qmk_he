# /// script
# dependencies = ["pyelftools"]
# ///
"""Import a completed standard QMK Make build into the same test harness."""
from pathlib import Path
import json
import shutil
import re
import os
from bat68_build_config import resolve_input
from bat68_build_config import BuildPaths
from bat68_artifacts import ROOT,write_manifest,dependencies,common_inputs


def import_build(locations,keymap="default"):
    qmk=locations.qmk;target="battle68_"+keymap
    build=locations.build
    config_path=build/"build_config.json"
    config=json.loads(config_path.read_text(encoding="utf-8"))
    generated=resolve_input(config["qmk_build_dir"],config) if "qmk_build_dir" in config else qmk/".build"
    # Retain lexical ../ components to recover assembly source paths from
    # QMK's obj.txt; normalize only when recording or opening final inputs.
    qmk_output=qmk/os.path.relpath(generated,qmk)
    intermediate=qmk_output/("obj_"+target)
    objects=[qmk/p for p in (intermediate/"obj.txt").read_text().split()]
    assert objects and all(p.is_file() for p in objects)
    inputs=set();sources=set()
    mtimes={}
    for obj in objects:
        dep=obj.with_suffix(".d")
        if not dep.is_file():
            # QMK's assembler rule does not emit a dependency file.
            source=(qmk/obj.relative_to(intermediate).with_suffix(".S")).resolve()
            assert source.is_file() and source.stat().st_mtime<=obj.stat().st_mtime+0.01,source
            sources.add(source);inputs.add(source);continue
        deps=dependencies([dep],qmk,locations);assert deps,dep
        # Reject an object that predates its current source/header content.
        for p in deps:
            if p not in mtimes:mtimes[p]=p.stat().st_mtime
        object_mtime=obj.stat().st_mtime
        assert all(mtimes[p]<=object_mtime+0.01 for p in deps),str(obj)
        inputs.update(deps)
        first=dep.read_text().replace("\\\n"," ").split()[1]
        source=(qmk/first).resolve();assert source.is_file(),source
        sources.add(source)
    inputs|=common_inputs(build,locations)
    inputs.update(p for p in (qmk/"platforms/sn34").rglob("*") if p.is_file())
    inputs.update((qmk/"lib/python/qmk/info.py",qmk/"data/schemas/keyboard.jsonschema",intermediate/"cflags.txt",intermediate/"ldflags.txt",intermediate/"obj.txt"))
    flags=(intermediate/"cflags.txt").read_text(encoding="utf-8")
    defines=set(re.findall(r"(?:^|\s)-D(\w+)",flags))
    required={"EEPROM_DRIVER","EEPROM_CUSTOM","VIA_ENABLE","RAW_ENABLE","NKRO_ENABLE","RGB_MATRIX_ENABLE"}
    if not required<=defines or "BOOTMAGIC_ENABLE" in defines:
        raise ValueError(f"Unexpected production feature flags: missing {required-defines}; Bootmagic must be disabled")
    if "-O2" not in flags.split():
        raise ValueError("Production QMK build must use the measured -O2 configuration")
    config["keymap"]=keymap
    config["feature_defines"]=sorted(defines)
    config_path.write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    shutil.copy2(qmk_output/(target+".elf"),build/"native_usb.elf")
    shutil.copy2(qmk_output/(target+".bin"),build/"native_usb.bin")
    shutil.copy2(qmk_output/(target+".map"),build/"native_usb.map")
    patches=json.loads((build/"patches.json").read_text())
    write_manifest(build,sources,inputs,"QMK CLI/Make",patches,locations)


def main():
    from build_bat68 import main as build_main
    import sys
    sys.argv.append("--import-only")
    build_main()


if __name__=="__main__":main()
