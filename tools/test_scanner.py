# /// script
# dependencies = ["unicorn"]
# ///
"""Compare the clean scanner implementation against the real stock ARM ISR."""
from pathlib import Path
import json
import os
import random
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
STOCK=(ROOT/"analysis/binary_2_rcdata_4000_0.bin").read_bytes()
LLVM=Path(os.environ.get("BAT68_LLVM",r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\ARM64\bin"))
STOP=0x100000

def machine(code):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x80000);u.mem_write(0,code)
    u.mem_map(0x20000000,0x28000);u.mem_map(0x40000000,0x100000)
    u.mem_map(STOP,0x1000)
    u.reg_write(UC_ARM_REG_SP,0x20027f00);u.reg_write(UC_ARM_REG_LR,STOP|1)
    return u

def main():
    build=ROOT/"build"
    elf=build/"scanner_test.elf"
    subprocess.run([str(LLVM/"clang.exe"),"--target=arm-none-eabi","-mcpu=cortex-m4","-mthumb",
                    "-ffreestanding","-fno-builtin","-Os","-Wall","-Wextra","-Werror","-nostdlib","-fuse-ld=lld",
                    "-Wl,-Ttext=0x19000","-Wl,-e,bat68_scatter_adc_phase",
                    str(ROOT/"firmware/board/bat68_scan.c"),"-o",str(elf)],check=True)
    subprocess.run([str(LLVM/"llvm-objcopy.exe"),"-O","binary",str(elf),str(build/"scanner_test.bin")],check=True)
    compiled=(build/"scanner_test.bin").read_bytes()
    image=bytearray(0x80000);image[0x19000:0x19000+len(compiled)]=compiled
    rng=random.Random(347)
    count=0
    for phase in range(8):
        for trial in range(8):
            adc=[rng.randrange(4096) for _ in range(18)]
            raw=[rng.randrange(65536) for _ in range(96)]
            old=machine(STOCK)
            old.mem_write(0x200003cc,bytes([phase]))
            old.mem_write(0x20003908,struct.pack("<96H",*raw))
            old.mem_write(0x40027000,struct.pack("<18I",*adc))
            old.mem_write(0x4002710c,struct.pack("<I",1))
            old.emu_start(0x761,STOP,count=5000)
            assert old.reg_read(UC_ARM_REG_PC)==STOP
            new=machine(bytes(image))
            new.mem_write(0x20001000,struct.pack("<18H",*adc))
            new.mem_write(0x20002000,struct.pack("<96H",*raw))
            new.reg_write(UC_ARM_REG_R0,0x20002000)
            new.reg_write(UC_ARM_REG_R1,0x20001000)
            new.reg_write(UC_ARM_REG_R2,phase)
            new.emu_start(0x19001,STOP,count=5000)
            assert new.reg_read(UC_ARM_REG_PC)==STOP
            assert old.mem_read(0x20003908,192)==new.mem_read(0x20002000,192),(phase,trial)
            count+=1
    xml_text=(ROOT/"analysis/calibration/keyboard.xml").read_text(encoding="utf-8")
    # OEM layout contains bare ampersands in its HID interface attribute.
    xml=ET.fromstring(re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', xml_text))
    names={int(e.attrib["key_index"]):e.attrib["name"] for e in xml.findall(".//key")}
    mapping=[]
    for electrical,layout in enumerate(STOCK[0x13f34:0x13fb4]):
        if layout==0x7d:continue
        group,slot=electrical&7,electrical>>3
        assert group<6
        mapping.append({"electrical":electrical,"layout_index":layout,"name":names.get(layout,"UNKNOWN"),"raw_slot":group*16+slot})
    result={"status":"PASS_OFFLINE_ONLY","stock_isr_equivalence_cases":count,"active_keys":len(mapping),"keys":mapping,
            "mux_gpio":["P0.9 (phase bit 0)","P3.0 (phase bit 1)","P3.1 (phase bit 2)"],
            "adc_irq":18,"adc_register_base":"0x40027000","adc_snapshot_ram":"0x20003908",
            "boot_entry":"USB upgrade request ultimately branches to 0x00200300 in the documented Boot region"}
    (ROOT/"analysis/board_map.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="keys"},indent=2))

if __name__=="__main__":main()
