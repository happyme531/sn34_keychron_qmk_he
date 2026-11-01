"""Fixed read-only diagnostic register list, resolved against the official SVD."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def register_list():
    svd=ET.parse(ROOT/"analysis/sdk/SONiX.SN34F2_DFP.2.0.4/SVD/SN34F280.svd")
    peripherals={p.findtext("name"):p for p in svd.findall(".//peripherals/peripheral")}
    words=[]
    def include(name,offsets,label=None,base=None):
        p=peripherals[name]
        if base is None:base=int(p.findtext("baseAddress"),0)
        for r in p.findall("registers/register"):
            offset=int(r.findtext("addressOffset"),0)
            if offset not in offsets:continue
            assert r.findtext("access")!="write-only",r.findtext("name")
            assert r.findtext("readAction") is None,r.findtext("name")
            words.append({"name":f"{label or name}.{r.findtext('name')}","address":base+offset})
    include("SN_SCU",{0,4,0x10,0x14,0x20,0x30,0x50,0x58,0x60,0x64,0x68,0x6c,0xbec}|set(range(0x800,0x844,4)))
    include("SN_ALWAYSON",set(range(0x200,0x230,4)))
    for port in range(4):include("SN_GPIO0",{0,4,8,0x18,0x1c,0x48},f"GPIO{port}",0x40037000+port*0x1000)
    include("SN_ADC0",set(range(0,18*4,4))|set(range(0x100,0x134,4))|{0x140,0x144,0x148,0x150,0x154,0x158})
    # No control/setup/data FIFO ports or DMA FIFO data ports are read.
    include("SN_USB_HS",{0x80,0x88,0xc0,0xc4,0x100,0x104,0x108,0x10c,0x110,0x114,0x120,0x124,
                         0x130,0x134,0x138,0x13c,0x140,0x144,0x148,0x14c,0x150,0x1d8,0x1dc}|
                        set(range(0x160,0x1c0,4))|set(range(0x1f0,0x200,4))|set(range(0x300,0x370,4)))
    include("SN_FLASH",{0,4,8,0xc,0x40,0x48,0x4c,0x50,0x58})
    for label,base,count in (("travel",0x200040d8,64),("idle",0x200046d8,64),
                             ("pressed",0x200047d8,64),("previous_raw",0x20004ff8,64),
                             ("current_raw",0x200050f8,64)):
        for index in range(count):words.append({"name":f"{label}.pair{index}","address":base+4*index})
    for index in range(16):words.append({"name":f"native_trial.word{index}","address":0x20011000+4*index})
    for index,item in enumerate(words):item["index"]=index
    assert len({v["address"] for v in words})==len(words)
    return words

REGISTERS=register_list()
