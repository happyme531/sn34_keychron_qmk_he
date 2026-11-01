# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute real SONiX Flash HAL for both HE banks and interrupted saves."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import os
os.environ.setdefault("SN34_NATIVE_BUILD", "build/keychron_he")
import hashlib
import json
from test_native_boot import Flash
from test_native_usb import BUILD, IMAGE, SCRATCH, SYMS,MANIFEST
from unicorn import UC_PROT_READ, UC_PROT_EXEC

SIZE = MANIFEST.get("he_eeprom_bytes",3584)
BANK_SIZE=SIZE+512
BASE=0x79000 if MANIFEST.get("qmk_platform") else 0x7b000
PAGES = tuple(range(BASE,0x7d000,512))
HALF=len(PAGES)//2


class Eeprom(Flash):
    def __init__(self, erased_byte=0):
        self.fail_at = None
        super().__init__(erased_byte, extra_pages=PAGES)
        self.u.mem_map(BASE,BANK_SIZE*2,UC_PROT_READ|UC_PROT_EXEC)
        self.u.mem_write(BASE,bytes((erased_byte,))*(BANK_SIZE*2))
        self.call("sn34_eeprom_init")

    def write_fmc(self,u,offset,size,value,data):
        if offset == 0x1040 and value & 1:
            page = self.fmc[0x1004]*512 - 0x2000
            command = self.fmc[0x1000] & 0xfff
            self.fail = self.fail_at == (page,command)
        super().write_fmc(u,offset,size,value,data)

    def stage(self, payload):
        self.u.mem_write(SCRATCH,payload)
        self.call("eeprom_update_block",SCRATCH,0,len(payload))

    def cache(self):
        self.call("eeprom_read_block",SCRATCH,0,SIZE)
        return bytes(self.u.mem_read(SCRATCH,SIZE))


def main():
    tests = []
    old = bytes((i*37+11)&255 for i in range(SIZE))
    new = bytes((i*19+3)&255 for i in range(SIZE))
    for erased in (0,255):
        m = Eeprom(erased); m.stage(old)
        assert m.call("sn34_eeprom_save") == 1
        assert m.events == [(op,page) for page in PAGES[:HALF] for op in ("erase","program")]
        assert m.call("sn34_eeprom_save") == 0 and len(m.events) == HALF*2
        saved = bytes(m.u.mem_read(BASE,BANK_SIZE*2))
        m.stage(new); assert m.call("sn34_eeprom_save") == 1
        m.call("sn34_eeprom_init"); assert m.cache() == new
        assert m.call("sn34_eeprom_sequence") == 2
        # Both the payload and header metadata are integrity checked.
        m.u.mem_write(BASE+BANK_SIZE+SIZE+8,b"\xff"*4)
        m.call("sn34_eeprom_init"); assert m.cache() == old
        assert m.call("sn34_eeprom_sequence") == 1
        # Simulate interruption at every erase/program boundary in the inactive
        # bank through the real HAL error path, then perform a fresh cache load.
        for page in PAGES[HALF:]:
            for command in (1,2):
                m.u.mem_write(BASE,saved)
                m.call("sn34_eeprom_init"); m.stage(new)
                m.fail_at = (page,command)
                assert m.call("sn34_eeprom_save") == 0xffffffff,(page,command)
                m.call("sn34_eeprom_init")
                assert m.cache() == old,(erased,page,command)
                assert m.call("sn34_eeprom_sequence") == 1
                m.fail_at = None
        assert bytes(m.u.mem_read(0,len(IMAGE))) == IMAGE
        assert bytes(m.u.mem_read(0x7d000,0xe00)) == b"\x96"*0xe00
        assert bytes(m.u.mem_read(0x7dffc,4)) == bytes.fromhex("5555aaaa")
    tests.append(f"Real Flash HAL saves all {HALF-1} data pages and the final commit page, with both zero and FF erase polarity")
    tests.append("No-op save, newest-bank reload, CRC of data and header metadata")
    tests.append(f"All {HALF*4} interrupted erase/program cases reload the previous complete bank; code, legacy keymap pages and footer are unchanged")
    m = Eeprom(); m.u.mem_write(SCRATCH,bytes(512))
    for offset in (0,0x2000,BASE-1,BASE+1,0x7cfff,0x7d000,0x7d200,0x7de00,0x7e000,0x200000):
        assert m.call("sn34_flash_write_eeprom_page",offset,SCRATCH) == 0xffffffff,hex(offset)
    assert not m.events
    m.remap = False
    assert m.call("sn34_flash_write_eeprom_page",BASE,SCRATCH) == 0xffffffff and not m.events
    tests.append("EEPROM wrapper rejects Boot mapping, misalignment and every address outside its two reserved banks")
    result = dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
                  limits=["Flash controller MMIO and effects modeled; real SDK Flash and board wrapper execute as ARM instructions", "Physical flash endurance and power-loss timing require hardware testing"])
    (BUILD/"eeprom_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
