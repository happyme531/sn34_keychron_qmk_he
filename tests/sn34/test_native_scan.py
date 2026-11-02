# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Compare native scan and mux behavior against captured v1.18 ISR reference data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"common"))
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

from model import load_board
import json
import hashlib
import random
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *
from emulator import Machine,ROOT,BUILD,SYMS,IMAGE,STOP,SCRATCH

class Peripheral:
    def __init__(self):
        self.regs={0x4001f80c:0x40000391,0x4001f804:0x50,0x4001f020:0x11000000}
        self.channels=[2000+i*13 for i in range(18)]
        self.adc_reset()
    def adc_reset(self):
        for key in list(self.regs):
            if 0x40027000<=key<0x40027400:self.regs.pop(key)
    def read(self,u,offset,size,data):
        address=0x40000000+offset
        assert size in (2,4),(hex(address),size)
        if 0x40027000<=address<0x40027048:return self.channels[(address-0x40027000)//4]
        if any(address==base+at for base in (0x40037000,0x40038000,0x40039000) for at in (0x10,0x14)):return 0
        return self.regs.get(address,0)
    def write(self,u,offset,size,value,data):
        address=0x40000000+offset
        assert size==4
        for base in (0x40037000,0x40038000,0x40039000):
            if address==base+0x10:self.regs[base]=self.regs.get(base,0)|value;return
            if address==base+0x14:self.regs[base]=self.regs.get(base,0)&~value;return
        if address in (0x4002710c,0x40027150):self.regs[address]=self.regs.get(address,0)&~value;return
        self.regs[address]=value
        if address==0x4001f81c and value&1:self.adc_reset()
        if address==0x40027100 and value&0x10:
            # Complete one ADC request. Calibration samples return offset 65.
            channel=self.regs.get(0x40027120,0)&31
            if self.regs.get(0x40027104,0)&0x80000000:self.channels[channel]=65
            self.regs[0x40027150]=self.regs.get(0x40027150,0)|(1<<channel)
            self.regs[0x4002710c]=self.regs.get(0x4002710c,0)|1
            self.regs[address]&=~0x10

class Native(Machine):
    def __init__(self):
        super().__init__();self.hw=Peripheral()
        self.u.mem_unmap(0x40000000,0x100000)
        self.u.mmio_map(0x40000000,0x100000,self.hw.read,None,self.hw.write,None)
        self.u.mem_map(0xe000e000,0x1000,UC_PROT_READ|UC_PROT_WRITE)
        self.u.mem_map(0xe0001000,0x1000,UC_PROT_READ|UC_PROT_WRITE)
    def work(self):
        return struct.unpack("<I",self.u.mem_read(SYMS["native_scan_work"],4))[0]
    def snapshot(self,output,frame):
        changed=self.call("native_scan_acquire",SCRATCH+1024,frame)
        if changed:
            pointer=struct.unpack("<I",self.u.mem_read(SCRATCH+1024,4))[0]
            self.u.mem_write(output,bytes(self.u.mem_read(pointer,192)))
            self.call("native_scan_release")
        return changed

class Stock:
    """Frozen raw/GPIO results captured by executing the original v1.18 ISR."""
    def __init__(self):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.mem_map(0x20000000,0x28000,UC_PROT_READ|UC_PROT_WRITE)
        self.hw=Peripheral()
        reference=ROOT/"tests/sn34/boards/battle68/fixtures/scan_reference_v118.json"
        self.reference=json.loads(reference.read_text(encoding="utf-8"))["phases"]
    def call(self,address,arg=0):
        assert address==0x760
        phase=self.u.mem_read(0x200003d4,1)[0]
        case=self.reference[phase]
        for slot,channel in case["samples"]:
            self.u.mem_write(0x200039f8+slot*2,struct.pack("<H",self.hw.channels[channel]))
        for address,bits in case["gpio"].items():
            address=int(address)
            self.hw.regs[address]=(self.hw.regs[address]&bits["keep"])|bits["set"]


def main():
    assert "ADC0_IRQHandler" in SYMS,"Build native USB with --scan first"
    native=Native()
    assert native.call("native_scan_init")==0
    assert native.hw.regs[0x40027140]==0,"Per-channel EOC sources must be masked for a whole-scan ISR"
    assert native.hw.regs[0x40027108]==1,"Only whole-scan completion should raise the board IRQ"
    assert (native.hw.regs[0x40027100]>>16)&31==14
    assert native.hw.regs[0x4002711c]&255==5
    for address,expected in ((0x40027120,0xc0d0a0b),(0x40027124,0x03040102),(0x40027128,0x070e0506)):
        assert native.hw.regs[address]==expected,(hex(address),hex(native.hw.regs[address]))
    rng=random.Random(118347)
    cases=0;mux_cases=0
    for phase in range(8):
        for trial in range(8):
            stock=Stock()
            data=[rng.randrange(4096) for _ in range(18)]
            raw=struct.pack("<96H",*[rng.randrange(65536) for _ in range(96)])
            stock.hw.channels=data.copy();stock.hw.regs[0x4002710c]=1
            for port in (0x40037000,0x40038000,0x40039000):
                value=rng.getrandbits(16);stock.hw.regs[port]=value;native.hw.regs[port]=value
            stock.u.mem_write(0x200003d4,bytes((phase,)));stock.u.mem_write(0x200039f8,raw)
            stock.call(0x760)
            native.hw.channels=data.copy();native.hw.regs[0x4002710c]=1
            native.u.mem_write(SYMS["native_scan_phase"],bytes((phase,)))
            work=native.work();native.u.mem_write(work,raw);native.call("ADC0_IRQHandler")
            assert native.u.mem_read(work,192)==stock.u.mem_read(0x200039f8,192),(phase,trial)
            for port in (0x40037000,0x40038000,0x40039000):
                assert native.hw.regs[port]==stock.hw.regs[port],(phase,hex(port))
            cases+=1
            mux_cases+=1
    coherent=Native();coherent.call("native_scan_init")
    coherent.u.mem_write(SCRATCH,bytes(196))
    for frame in range(2):
        for phase in range(8):
            coherent.hw.channels=[2200-frame*50-phase*10-i for i in range(18)]
            work=coherent.work()
            coherent.hw.regs[0x4002710c]=1;coherent.call("ADC0_IRQHandler")
            if phase<7:
                assert coherent.snapshot(SCRATCH,SCRATCH+192)==0
        expected=bytes(coherent.u.mem_read(work,192))
        assert coherent.snapshot(SCRATCH,SCRATCH+192)==1
        assert bytes(coherent.u.mem_read(SCRATCH,192))==expected
        assert coherent.snapshot(SCRATCH,SCRATCH+192)==0
    coherent.u.mem_write(SCRATCH+516,b"\xff"*4)
    assert coherent.call("native_scan_acquire",SCRATCH+512,SCRATCH+516)==1
    held=struct.unpack("<I",coherent.u.mem_read(SCRATCH+512,4))[0]
    held_data=bytes(coherent.u.mem_read(held,192))
    for frame in range(4):
        for phase in range(8):
            work=coherent.work();assert work!=held
            coherent.hw.channels=[1800-frame*50-phase*10-i for i in range(18)]
            coherent.hw.regs[0x4002710c]=1;coherent.call("ADC0_IRQHandler")
            assert bytes(coherent.u.mem_read(held,192))==held_data
    newest=bytes(coherent.u.mem_read(work,192))
    coherent.call("native_scan_release")
    assert coherent.call("native_scan_acquire",SCRATCH+512,SCRATCH+516)==1
    current=struct.unpack("<I",coherent.u.mem_read(SCRATCH+512,4))[0]
    assert bytes(coherent.u.mem_read(current,192))==newest
    coherent.call("native_scan_release")
    mapping=load_board()['keys']
    used={key['raw_slot'] for key in mapping};coverage=set()
    # Generation overflow must not re-enter the full-channel startup sequence.
    native.u.mem_write(SYMS['native_scan_frames'],bytes.fromhex('ffffffff'))
    for next_phase in range(8):
        native.u.mem_write(SYMS['native_scan_phase'],bytes(((next_phase-1)%8,)))
        native.hw.regs[0x4002710c]=1;native.call('ADC0_IRQHandler')
        upper=next_phase>>2;pair=(next_phase&3)*2
        wiring=((10,11,12,13),(1,2,3,4),(5,6,7,14))
        live={wiring[group][lane^upper]:group*32+upper*16+(lane>>1)*8+pair+(lane&1)
              for group in range(3) for lane in range(4)
              if group*32+upper*16+(lane>>1)*8+pair+(lane&1) in used}
        coverage.update(live.values())
        count=((native.hw.regs[0x40027100]>>16)&31)+1
        ranks=[(native.hw.regs[0x40027120+(i//4)*4]>>((i%4)*8))&31 for i in range(count)]
        assert ranks[0]==11 and set(ranks[1:])==set(live) and len(ranks)==len(live)+1
    assert coverage==used,'Phase-specific ADC ranks must cover every physical switch'
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),"adc_scatter_equivalence_cases":cases,"mux_gpio_equivalence_cases":mux_cases,
            "sdk_adc_init_executed":True,"tests":["Official HAL ADC init/calibration and 15-channel sequence",
            "All eight native raw-scan phases match the captured v1.18 ISR results", "Mux pins match v1.18 function 0x450c"]+
            ["Only complete eight-phase frames are published and consumed once",
             "A leased frame remains byte-exact through four producer frames; after release the consumer receives the newest complete frame",
             "Phase-specific ADC ranks retain a dummy conversion and cover all 67 physical switches exactly once per frame"],
            "limits":["ADC completion is modeled; analog behavior, timing and actual readings require hardware validation"]}
    (BUILD/"scan_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
