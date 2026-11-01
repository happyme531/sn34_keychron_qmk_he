# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Compare native scan and mux behavior against the real v1.18 Thumb code."""
import json
import hashlib
import random
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import *
from test_native_usb import Machine,ROOT,BUILD,SYMS,IMAGE,STOP,SCRATCH

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
        if "native_scan_work" in SYMS:
            return struct.unpack("<I",self.u.mem_read(SYMS["native_scan_work"],4))[0]
        return SYMS["native_raw"]
    def snapshot(self,output,frame):
        if "native_scan_snapshot" in SYMS:return self.call("native_scan_snapshot",output,frame)
        changed=self.call("native_scan_acquire",SCRATCH+1024,frame)
        if changed:
            pointer=struct.unpack("<I",self.u.mem_read(SCRATCH+1024,4))[0]
            self.u.mem_write(output,bytes(self.u.mem_read(pointer,192)))
            self.call("native_scan_release")
        return changed

class Stock:
    def __init__(self):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        image=(ROOT/"analysis/v118_rcdata_4000.bin").read_bytes()
        self.u.mem_map(0,0x80000,UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(0,image)
        self.u.mem_map(0x20000000,0x28000,UC_PROT_READ|UC_PROT_WRITE)
        self.u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.hw=Peripheral();self.u.mmio_map(0x40000000,0x100000,self.hw.read,None,self.hw.write,None)
        self.u.hook_add(UC_HOOK_CODE,self.code)
    def code(self,u,address,size,data):
        # Only travel processing and pinmux helpers are skipped; the stock ADC
        # register reads, all raw writes and its GPIO mux switch execute.
        if address in (0xedc,0xf688,0x48c0,0x4acc):u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def call(self,address,arg=0):
        self.u.reg_write(UC_ARM_REG_R0,arg);self.u.reg_write(UC_ARM_REG_R4,0)
        self.u.reg_write(UC_ARM_REG_SP,0x20027f00);self.u.reg_write(UC_ARM_REG_LR,STOP|1)
        self.u.emu_start(address|1,STOP,count=20000)
        assert self.u.reg_read(UC_ARM_REG_PC)==STOP

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
    if "native_adc_cycles" in SYMS:
        timestamps=[]
        def timing_read(u,access,address,size,value,data):
            if address in (0xe0001004,SYMS["native_usb_irq_cycles"]):
                assert u.reg_read(UC_ARM_REG_PRIMASK)==1,"ADC/USB timing snapshots must exclude higher-priority USB preemption"
                timestamps.append(address)
        hook=native.u.hook_add(UC_HOOK_MEM_READ,timing_read)
        native.hw.regs[0x4002710c]=1;native.call("ADC0_IRQHandler")
        native.u.hook_del(hook)
        assert timestamps.count(0xe0001004)==2 and timestamps.count(SYMS["native_usb_irq_cycles"])==2
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
    if "native_scan_snapshot" in SYMS or "native_scan_acquire" in SYMS:
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
        if "native_scan_acquire" in SYMS:
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
    if "native_scan_configure" in SYMS:
        # Reconfigure only at a complete-frame boundary, and restore all 15
        # original ranks when leaving compact mode, including through mode 0.
        mapping=json.loads((BUILD/"board.json").read_text())
        used={key["raw_slot"] for key in mapping};coverage=set()
        for mode in (0,7,3,1,7,0,1):
            assert native.call("native_scan_configure",mode)==0
            for phase in range(8):
                native.u.mem_write(SYMS["native_scan_phase"],bytes((phase,)))
                native.hw.regs[0x4002710c]=1;native.call("ADC0_IRQHandler")
                if phase==7:
                    assert native.u.mem_read(SYMS["native_scan_mode"],1)[0]==mode
                active=native.u.mem_read(SYMS["native_scan_mode"],1)[0]
                if active==7:
                    next_phase=(phase+1)&7;upper=next_phase>>2;pair=(next_phase&3)*2
                    wiring=((10,11,12,13),(1,2,3,4),(5,6,7,14))
                    live={wiring[group][lane^upper]:group*32+upper*16+(lane>>1)*8+pair+(lane&1)
                          for group in range(3) for lane in range(4)
                          if group*32+upper*16+(lane>>1)*8+pair+(lane&1) in used}
                    coverage.update(live.values())
                    count=((native.hw.regs[0x40027100]>>16)&31)+1
                    ranks=[(native.hw.regs[0x40027120+(i//4)*4]>>((i%4)*8))&31 for i in range(count)]
                    assert ranks[0]==11 and set(ranks[1:])==set(live) and len(ranks)==len(live)+1
                elif phase==7:
                    assert (native.hw.regs[0x40027100]>>16)&31==(12 if mode==3 else 14)
        assert coverage==used,"Phase-specific ADC sequences must cover every physical switch"
        assert native.call("native_scan_configure",2)==0xffffffff
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),"adc_scatter_equivalence_cases":cases,"mux_gpio_equivalence_cases":mux_cases,
            "sdk_adc_init_executed":True,"tests":["Official HAL ADC init/calibration and 15-channel sequence",
            "All eight native raw-scan phases match the real v1.18 ISR", "Mux pins match v1.18 function 0x450c"]+
            (["Only complete eight-phase frames are published and consumed once"] if "native_scan_snapshot" in SYMS or "native_scan_acquire" in SYMS else [])+
            (["A leased frame remains byte-exact through four producer frames; after release the consumer receives the newest complete frame",
              "Phase-specific ADC ranks retain a dummy conversion and cover all 67 physical switches exactly once per frame",
              "Both ADC/USB timestamp pairs are captured with interrupts masked, preventing nested-IRQ double accounting"] if "native_scan_acquire" in SYMS else []),
            "limits":["ADC completion is modeled; analog behavior, timing and actual readings require hardware validation"]}
    (BUILD/"scan_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
