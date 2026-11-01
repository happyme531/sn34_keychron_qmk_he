# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Run the native Flash HAL and check the captured retained-Boot footer contract."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"common"))
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import hashlib
import json
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *
from emulator import Machine,ROOT,BUILD,SYMS,IMAGE,STOP,BASE,MANIFEST

class Flash(Machine):
    def __init__(self,erased_byte=0,extra_pages=()):
        super().__init__()
        self.erased_byte=erased_byte
        self.allowed_pages={0x7d000,0x7d200,0x7de00,*extra_pages}
        self.u.mem_map(0x7d000,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.u.mem_write(0x7d000,b"\x96"*0x1000)
        self.u.mem_write(0x7dffc,bytes.fromhex("5555aaaa"))
        self.u.mem_unmap(0x40000000,0x100000)
        self.remap=True;self.stuck=False;self.fail=False
        self.core={};self.cycles=0;self.fmc={};self.events=[];self.fifo=bytearray(512)
        self.u.mmio_map(0x40000000,0x100000,self.read_peripheral,None,self.write_peripheral,None)
        self.u.mmio_map(0xe0000000,0x20000,self.read_core,None,self.write_core,None)
        self.u.mmio_map(0x00600000,0x2000,self.read_fmc,None,self.write_fmc,None)
        self.call("native_time_init")
    def read_peripheral(self,u,offset,size,data):return (1<<24) if offset==0x1f020 and self.remap else 0
    def write_peripheral(self,u,offset,size,value,data):raise AssertionError(f"Unexpected peripheral write {offset:#x}")
    def read_core(self,u,offset,size,data):
        if offset==0x1004:self.cycles=(self.cycles+12000)&0xffffffff;return self.cycles
        return self.core.get(offset,0)
    def write_core(self,u,offset,size,value,data):
        assert offset in (0x1000,0xedfc),hex(offset)
        self.core[offset]=value
    def read_fmc(self,u,offset,size,data):
        if offset==0x1048 and self.stuck:return 1
        return self.fmc.get(offset,0)
    def write_fmc(self,u,offset,size,value,data):
        if offset<512:self.fifo[offset:offset+size]=value.to_bytes(size,"little");return
        assert offset in (0x1000,0x1004,0x1040,0x1050,0x1058),hex(offset)
        if offset==0x1050:self.fmc[offset]=self.fmc.get(offset,0)&~value;return
        self.fmc[offset]=value
        if offset!=0x1040 or not value&1:return
        command=self.fmc[0x1000]&0xfff;page=self.fmc[0x1004]*512-0x2000
        assert page in self.allowed_pages,f"Erase escaped allowed User pages: {page:#x}"
        assert command in (1,2),hex(command)
        if self.fail:self.fmc[0x1040]=0;self.fmc[0x1050]=2;return
        if command==1:u.mem_write(page,bytes((self.erased_byte,))*512);self.events.append(("erase",page))
        else:u.mem_write(page,bytes(self.fifo));self.events.append(("program",page))
        self.fmc[0x1040]=0;self.fmc[0x1050]=1

class BootDecision:
    """Previously executed Boot decisions, without redistributing the Boot image."""
    def __init__(self,footer,option):
        path=ROOT/"tests/sn34/boards/battle68/fixtures/boot_reference.json"
        self.reference=json.loads(path.read_text(encoding="utf-8"))
        self.footer,self.option=footer,option
        self.source_sha256=self.reference["source_sha256"]
    def run(self):
        return next(case["result"] for case in self.reference["cases"]
                    if (case["footer"],case["option"])==(self.footer,self.option))


def main():
    tests=[]
    if MANIFEST.get("qmk_platform"):
        cold=Machine();cold.u.mem_map(0xe000e000,0x2000,UC_PROT_READ|UC_PROT_WRITE)
        size=SYMS["__data_end"]-SYMS["__data_start"]
        bss_size=SYMS["__bss_end"]-SYMS["__bss_start"]
        expected=bytes(cold.u.mem_read(SYMS["__data_load"],size))
        cold.u.mem_write(SYMS["__data_start"],bytes((0xa5,))*size)
        cold.u.mem_write(SYMS["__bss_start"],bytes((0xa5,))*bss_size)
        def stop_at_main(u,address,size,data):
            if address==(SYMS["main"]&~1):u.emu_stop()
        cold.u.hook_add(UC_HOOK_CODE,stop_at_main)
        cold.u.reg_write(UC_ARM_REG_SP,0x20027fc0)
        cold.u.emu_start(SYMS["native_reset"]|1,STOP,count=2000000)
        assert cold.u.reg_read(UC_ARM_REG_PC)==(SYMS["main"]&~1)
        assert bytes(cold.u.mem_read(SYMS["__data_start"],size))==expected
        assert not any(cold.u.mem_read(SYMS["__bss_start"],bss_size))
        assert cold.u.reg_read(UC_ARM_REG_PRIMASK)==1
        tests.append("Actual cold-reset code restores all initialized data and frame-buffer pointers and clears BSS before main, with interrupts still masked")
    for erased_byte in (0,255):
        f=Flash(erased_byte);before=bytes(f.u.mem_read(0x7d000,0x1000))
        assert f.call("sn34_flash_invalidate_application")==0
        assert f.events==[("erase",0x7de00)],f.events
        after=bytes(f.u.mem_read(0x7d000,0x1000))
        assert after[:0xe00]==before[:0xe00] and after[0xe00:]==bytes((erased_byte,))*512
        assert bytes(f.u.mem_read(BASE,len(IMAGE)))==IMAGE
    tests.append("Actual SDK Flash HAL erases only the final unused 512-byte User page, preserving settings and executable code; accepts zero or FF erase polarity")
    for condition in ("boot_mapping","busy","erase_error"):
        m=Flash()
        if condition=="boot_mapping":m.remap=False
        elif condition=="busy":m.stuck=True
        else:m.fail=True
        assert m.call("sn34_flash_invalidate_application")!=0
        assert not m.events and bytes(m.u.mem_read(0x7dffc,4))==bytes.fromhex("5555aaaa")
    tests.append("Boot mapping, a stuck controller and erase failure reject entry without modifying the valid footer")
    if "sn34_flash_validate_application" in SYMS:
        m=Flash();assert m.call("sn34_flash_invalidate_application")==0
        assert m.call("sn34_flash_validate_application")==0
        assert m.events==[("erase",0x7de00),("erase",0x7de00),("program",0x7de00)]
        assert bytes(m.u.mem_read(0x7de00,512))==bytes(508)+bytes.fromhex("5555aaaa")
        assert bytes(m.u.mem_read(0x7d000,0xe00))==b"\x96"*0xe00
        tests.append("Guard commit restores exactly the reserved footer page through the real SDK HAL and leaves both settings pages untouched")
    for option in (0,4):
        assert BootDecision(0xaaaa5555,option).run()=="USER_REBOOT"
        for footer in (0xffffffff,0):assert BootDecision(footer,option).run()=="USB_ISP"
    tests.append("Captured retained-Boot decisions select USB ISP for an absent footer for both factory option-bit states; valid footer selects User")
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),"tests":tests,
            "boot_sha256":BootDecision(0,0).source_sha256,"boot_decision_evidence":"Captured reference table; Boot executable is not rerun by this test",
            "limits":["FMC hardware effects and the Boot's hardware initialization are modeled; real reset, USB Boot enumeration and OEM OTA require hardware validation"]}
    (BUILD/"boot_test_results.json").write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=="__main__":main()
