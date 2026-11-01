# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Validate production USB descriptors, protocol fallback and lighting output."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"util/sn34"))

import json
import hashlib
import struct
import re
from test_bat68 import Keyboard,BUILD,IMAGE,SYMS,SCRATCH,NAMES,PROFILES,KEYS,CURVE_STEPS
from test_native_usb import source_code_address
from build_config import ROOT


def hid_sizes(desc):
    at=0;rid=0;size=count=0;inputs={};outputs={}
    while at<len(desc):
        prefix=desc[at];n=prefix&3;n=4 if n==3 else n
        value=int.from_bytes(desc[at+1:at+1+n],"little")
        kind=prefix&0xfc
        if kind==0x84:rid=value
        elif kind==0x74:size=value
        elif kind==0x94:count=value
        elif kind==0x80:inputs[rid]=inputs.get(rid,0)+size*count
        elif kind==0x90:outputs[rid]=outputs.get(rid,0)+size*count
        at+=n+1
    return {r:(bits+7)//8+(r!=0) for r,bits in inputs.items()},{r:(bits+7)//8+(r!=0) for r,bits in outputs.items()}


def main():
    tests=[];m=Keyboard()
    compat=json.loads((ROOT/"tests/sn34/boards/battle68/fixtures/sn34_v36_compatibility.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((BUILD/"rgb_protocol.json").read_bytes()).hexdigest()==compat["rgb_protocol_sha256"]
    vectors=struct.unpack_from("<112I",IMAGE)
    assert vectors[0]==0x20027fc0 and vectors[1]==SYMS["sn34_reset_entry"]
    for irq,name in ((3,"SCU_IRQHandler"),(18,"ADC0_IRQHandler"),(56,"DMA1_CH0_IRQHandler"),(77,"USB_HS_IRQHandler")):
        assert vectors[16+irq]==SYMS[name],(irq,name)
    assert all(source_code_address(value&~1) for value in vectors[1:])
    via=json.loads((BUILD/"sn34_via.json").read_text())
    keys=[s for row in via["layouts"]["keymap"] for s in row if isinstance(s,str)]
    mapping=json.loads((BUILD/"board.json").read_text())
    assert len(keys)==len(set(keys))==67
    assert set(keys)=={f"{k['matrix'][0]},{k['matrix'][1]}" for k in mapping}
    tests.append("All interrupt vectors reference source code; VIA definition exposes exactly the 67 configured switch positions")
    launcher=json.loads((BUILD/"sn34_launcher.json").read_text())
    assert launcher["feature"]==["HE"] and launcher["vendorProductId"]==(0x0c45<<16|0x8037)
    assert {(k["row"],k["col"]) for k in launcher["layouts"]["keys"]}=={tuple(k["matrix"]) for k in mapping}
    assert launcher["layers"]==["主层","Fn","苹果主层","苹果 Fn"]
    assert not any("win" in name.lower() or "mac" in name.lower() for name in launcher["layers"])
    assert m.raw_command(bytes((0xa0,)))[:4]==bytes((0xa0,2,0,2))
    version=m.raw_command(bytes((0xa1,)))[1:]
    assert b"\0" in version and re.fullmatch(rb"v2\.0\.0 \d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}",version.split(b"\0",1)[0]),version
    assert m.raw_command(bytes((0xa2,)))[:4]==bytes((0xa2,0,9,2))
    assert m.raw_command(bytes((0xa3,)))[:3]==bytes((0xa3,0,0))
    assert m.raw_command(bytes((0xa7,1)))[:6]==bytes((0xa7,1,0,2,0,128))
    assert m.raw_command(bytes((0xa7,0x12)))[:4]==bytes((0xa7,0x12,0,3))
    assert m.raw_command(bytes((0xa7,0x13,0)))[2]==0
    assert m.raw_command(bytes((0xa7,0x12)))[3]==2
    assert m.raw_command(bytes((0xa7,0x13,1)))[2]==0
    assert m.raw_command(bytes((0xa7,0x13,2)))[2]==1
    assert m.raw_command(bytes((0xa7,0x0f)))[0]==255
    tests.append("Official Launcher identity, capability and NKRO packets follow Keychron byte order; unavailable wireless, Quick Start, custom RGB and DFU are not advertised")
    profile_info=m.raw_command(bytes((0xa9,0x10)))
    profile_size=int.from_bytes(profile_info[4:6],"little")
    for profile in range(3):
        offset=profile_size-32
        request=bytes((0xa9,0x12,profile,offset&255,offset>>8,30))
        canary=bytes(range(16));m.u.mem_write(SCRATCH+32,canary)
        reply=m.raw_command(request)
        assert reply[:6]==request and bytes(m.u.mem_read(SCRATCH+32,16))==canary
        normal=m.raw_command(request[:5]+bytes((26,)))
        assert reply[6:]==normal[6:]
    tests.append("Official Launcher 30-byte profile-name requests return the available 26-byte payload and preserve a canary after the packet")
    r,c=NAMES["A"]["matrix"]
    assert m.raw_command(bytes((0xa9,0x15,0,2,r,c,13)))[2]==0
    m.press("A")
    reply=m.raw_command(bytes((2,3,r)))
    assert int.from_bytes(reply[3:5],"big")&(1<<c),reply.hex()
    assert m.raw_command(bytes((0xa9,0x20)))[0]==0xa9
    assert m.raw_command(bytes((0xa9,0x22)))[0]==0xa9
    assert m.raw_command(bytes((0xa7,0x13,0)))[2]==1
    m.release("A")
    assert m.raw_command(bytes((0xa9,0x15,0,0,r,c,0)))[2]==0
    tests.append("Launcher key test reads the physical Hall matrix even for gamepad keys; read-only HE queries work while held and NKRO changes wait for release")
    assert m.setup(0x80,6,0x0200,0,512)==0
    config=m.transfers[-1][1];assert config[4]==6
    assert struct.unpack_from("<H",config,2)[0]==len(config)
    at=0;interfaces=[];eps=[]
    while at<len(config):
        n,t=config[at:at+2];assert n>=2
        if t==4:interfaces.append(config[at+2])
        if t==5:eps.append(config[at+2])
        at+=n
    assert interfaces==list(range(6)) and eps==[0x81,0x82,0x83,3,0x85,5,0x86,6],(interfaces,eps)
    expected={0:{0:8},1:{2:6,3:3,4:3,6:32,7:11},4:{0:32}}
    for interface,sizes in expected.items():
        assert m.setup(0x81,6,0x2200,interface,1024)==0
        inputs,outputs=hid_sizes(m.transfers[-1][1]);assert inputs==sizes,(interface,inputs)
        if interface==1:assert outputs=={6:2}
    assert m.setup(0x80,6,0x03ee,0x0409,18)==0
    assert m.transfers[-1][1][2:16]=="MSFT100".encode("utf-16le")
    assert m.setup(0xc0,0x20,0,4,40)==0
    compat=m.transfers[-1][1];assert len(compat)==40 and compat[16]==5 and compat[18:24]==b"XUSB10"
    tests.append("Six USB interfaces and exact report sizes, plus a distinct XUSB vendor interface and Microsoft compatible-ID descriptors")
    actual=Keyboard(real_usb_endpoints=True)
    assert len([x for x in actual.endpoints if x[0]&15])==8,actual.endpoints
    assert actual.call("HAL_PCD_EP_Open",SYMS["hPCD"],4,64,3)!=0
    tests.append("Real PCD HAL and OTGPE allocator configure all eight hardware FIFOs and reject a ninth endpoint")
    recovery=Keyboard(real_usb_endpoints=True,configure=False)
    recovery.step(4987)
    assert bytes(recovery.u.mem_read(SYMS["enumeration_phase"],1))==b"\0"
    recovery.step(1)
    assert recovery.usb_link[-1][0]=="HAL_PCD_Stop"
    recovery.step(299)
    assert recovery.usb_link[-1][0]=="HAL_PCD_Stop"
    recovery.step(1)
    assert recovery.usb_link[-2][0:2]==("HAL_PCD_ForceFullSpeed",1)
    assert recovery.usb_link[-1][0]=="HAL_PCD_Start"
    assert recovery.setup(0x80,6,0x0100,0,18)==0
    assert recovery.setup(0x80,6,0x0200,0,512)==0
    assert recovery.setup(0,5,7)==0 and recovery.setup(0,9,1)==0
    for _ in range(12):recovery.step()
    recovery.press("A");assert recovery.pressed(4);recovery.release("A")
    # Reset and reconfigure using the real allocator; endpoint FIFO resources
    # must be released rather than leaking across the reconnection.
    recovery.call("HAL_PCD_ResetCallback",0)
    assert recovery.setup(0,5,7)==0 and recovery.setup(0,9,1)==0
    before=len(recovery.usb_link);recovery.step(20000)
    assert len(recovery.usb_link)==before
    recovery.call("sn34_usb_diagnostics",SCRATCH)
    diag=bytes(recovery.u.mem_read(SCRATCH,24))
    assert diag[0]==1 and diag[3:6]==bytes((2,1,0)) and struct.unpack_from("<I",diag,8)[0]>=1
    failed=Keyboard(configure=False);failed.step(5000);failed.step(300)
    before=len(failed.usb_link);failed.step(20000);assert len(failed.usb_link)==before
    before=len(m.usb_link);m.step(20000);assert len(m.usb_link)==before
    tests.append("Initial enumeration failure detaches for 300 ms then retries once at Full Speed; all eight real FIFOs reconfigure after reset, diagnostics record recovery and healthy links never retry")
    assert m.call("rgb_matrix_is_enabled")==1 and m.call("rgb_matrix_get_val")==32
    tests.append("RGB starts enabled at brightness 32 with the solid-color default")
    def rendered_frame():
        before=len(m.spi)
        for _ in range(100):
            m.step(1)
            if len(m.spi)>before:return
        raise AssertionError("RGB did not complete a frame within 100 task iterations")
    # Finish startup rendering before changing the live RGB configuration.
    # A frame now spans more task calls because input work gets priority.
    rendered_frame()
    assert m.raw_command(bytes((7,3,1,255)))[0]==7
    assert m.raw_command(bytes((7,3,4,0,0)))[0]==7
    assert m.raw_command(bytes((7,3,2,1)))[0]==7
    rendered_frame();rendered_frame()
    assert m.call("rgb_matrix_get_val")==255
    assert m.spi[-1][120:-120]==bytes((0xee,))*(67*12),"Full white must encode FF FF FF for every LED"
    tests.append("VIA brightness 255 and solid white produce exact 0xFFFFFF GRB data for all 67 LEDs without a hidden brightness cap")
    effects=json.loads((BUILD/"rgb_effects.json").read_text())
    rgb_protocol=json.loads((BUILD/"rgb_protocol.json").read_text())
    options=launcher["menus"][0]["content"][0]["content"][1]["options"]
    assert len(effects)==48 and [o[1] for o in options]==list(range(23))+list(range(25,51))
    assert via["menus"]==launcher["menus"]
    for item in rgb_protocol:
        wire,core=item["wire"],item["core"]
        assert m.raw_command(bytes((7,3,2,wire)))[:4]==bytes((7,3,2,wire))
        assert m.raw_command(bytes((8,3,2)))[:4]==bytes((8,3,2,wire))
        if core:assert m.call("rgb_matrix_get_mode")==core,(wire,core,item["name"])
        else:assert not m.call("rgb_matrix_is_enabled")
    before=m.call("rgb_matrix_get_mode")
    for wire in (23,24,51,255):
        assert m.raw_command(bytes((7,3,2,wire)))[0]==255
        assert m.call("rgb_matrix_get_mode")==before
    for mode in range(1,len(effects)+1):
        m.call("rgb_matrix_mode_noeeprom",mode)
        assert m.call("rgb_matrix_get_mode")==mode,(mode,effects[mode-1])
        before=len(m.spi)
        rendered_frame()
        assert len(m.spi)>before,(mode,effects[mode-1],"No rendered frame")
    m.call("rgb_matrix_mode_noeeprom",255)
    assert m.call("rgb_matrix_get_mode")==len(effects),"Menu count differs from the compiled enum"
    m.call("rgb_matrix_mode_noeeprom",1)
    tests.append("All 48 RGB effects render; every Launcher/VIA wire ID round-trips to its intended QMK effect, reserving special editor IDs 23/24")
    # Check real Chinese dictionary IDs independently of the generated map.
    expected={2:"BREATHING",3:"BAND_SPIRAL_VAL",4:"CYCLE_ALL",18:"SOLID_REACTIVE_SIMPLE",21:"SPLASH",22:"SOLID_SPLASH"}
    for wire,name in expected.items():
        m.raw_command(bytes((7,3,2,wire)))
        assert effects[m.call("rgb_matrix_get_mode")-1]==name
    m.raw_command(bytes((7,3,4,0,255)));m.call("rgb_matrix_set_speed_noeeprom",128)
    m.call("rgb_matrix_mode_noeeprom",effects.index("ALPHAS_MODS")+1)
    for _ in range(10):m.step(40)
    # g_led_config contains 96 matrix indices, 134 coordinate bytes, 67 flags.
    config=bytes(m.u.mem_read(SYMS["g_led_config"],96+134+67))
    frames=m.spi[-1][120:-120]
    led=lambda name:config[NAMES[name]["matrix"][0]*16+NAMES[name]["matrix"][1]]
    assert frames[led("A")*12:led("A")*12+12]!=frames[led("Fn")*12:led("Fn")*12+12]
    tests.append("Canonical Launcher effect numbers match its dictionary; Alphas Mods renders different colors for letters and modifier/Fn LEDs")
    # Stock table quadrants are strongly nonlinear: equal travel produces
    # increasingly large ADC drops. Run the compiled converter on all stock
    # knots for every key, including endpoints and values outside them.
    cumulative=[0]
    for step in CURVE_STEPS:cumulative.append(cumulative[-1]+step)
    assert [cumulative[i] for i in (0,41,82,123,165)]==[0,82,193,391,777]
    for key in KEYS:
        p=PROFILES[key["raw_slot"]];zero,bottom=p["idle"],p["pressed"]
        previous=-1
        for i,drop in enumerate(cumulative):
            raw=zero-round(drop*(zero-bottom)/777)
            actual=m.call("sn34_hall_convert",raw,zero,bottom)
            assert abs(actual-i*240/165)<=2,(key["name"],i,actual)
            assert actual>=previous;previous=actual
        assert m.call("sn34_hall_convert",zero+20,zero,bottom)==0
        assert m.call("sn34_hall_convert",bottom-20,zero,bottom)==240
    assert m.call("sn34_hall_convert",1000,1000,1000)==0
    assert m.call("sn34_hall_convert",1000,1000,2000)==0
    r,c=NAMES["A"]["matrix"]
    for travel in (0,60,120,180,240):
        m.travel("A",travel)
        assert abs(m.call("analog_matrix_get_travel",r,c)-travel)<=2
    m.release("A")
    tests.append("All 67 Hall curves are monotone, bounded and within two normalized units at every stock knot; real HE scanning uses the nonlinear conversion")
    start=len(m.transfers)
    ep,buffer,size=next(x for x in reversed(m.receives) if x[0]==5)
    assert size==32
    m.u.mem_write(buffer,bytes((1,))+bytes(31));m.rx_lengths[5]=32
    m.call("HAL_PCD_DataOutStageCallback",0,5);m.call("raw_hid_task");m.drain()
    assert any(ep==0x85 and p[:3]==bytes((1,0,12)) for ep,p in m.transfers[start:])
    tests.append("Raw HID OUT endpoint completion reaches the upstream VIA handler and returns its 32-byte reply through the host queue")
    assert m.setup(0x21,11,0,0,0)==0 # Boot protocol
    m.call("native_usb_task")
    start=len(m.transfers);m.press("A");m.release("A")
    boot=[p for ep,p in m.transfers[start:] if ep==0x81]
    assert boot and any(4 in p[2:] for p in boot) and boot[-1]==bytes(8)
    assert m.setup(0x21,11,1,0,0)==0
    m.call("native_usb_task");m.press("A");assert m.pressed(4);m.release("A")
    tests.append("HID SET_PROTOCOL switches from NKRO to BIOS boot reports and back")
    # This callback sets the SDK to Full Speed, as on a USB 1.x host/hub.
    m.call("HAL_PCD_ResetCallback",0)
    assert m.setup(0,5,7)==0 and m.setup(0,9,1)==0
    assert all(packet<=64 for ep,packet,kind in m.endpoints if ep&0x80==0)
    m.step();m.press("A");assert m.pressed(4);m.release("A")
    tests.append("Full Speed configuration accepts every endpoint, including the OTA interface, and continues normal typing")
    # Indicators use board pins independently of the RGB chain order.
    m.u.mem_write(SYMS["native_keyboard_leds"],b"\x02")
    m.call("sn34_indicators_task")
    assert int.from_bytes(m.u.mem_read(0x40038010,4),"little")==(1<<6)
    # RGB SPI stream is checked against an independent bit-string encoder.
    assert m.u.mem_read(SYMS["initialized"],1)==b"\x01","RGB HAL initialization failed"
    baseline=len(m.spi)
    m.call("rgb_matrix_set_color_all",0,0,0)
    m.call("rgb_matrix_set_color",3,0x12,0x34,0x56)
    m.call("flush");assert m.spi
    stream=m.spi[-1];assert len(stream)==1044 and stream[:120]==bytes(120) and stream[-120:]==bytes(120)
    expected=b""
    for value in (0x34,0x12,0x56):
        encoded="".join("1110" if value&(1<<bit) else "1000" for bit in range(7,-1,-1))
        expected+=int(encoded,2).to_bytes(4,"big")
    assert stream[120+3*12:120+4*12]==expected,(stream[120+3*12:120+4*12].hex(),expected.hex())
    m.call("rgb_matrix_set_color",3,255,0,0)
    m.call("flush");assert len(m.spi)==baseline+1,"Busy DMA must not overwrite its active buffer"
    m.call("HAL_SPI_TxCpltCallback",SYMS["rgb_spi"]);m.call("flush");assert len(m.spi)==baseline+2
    tests.append("WS2812 GRB encoding, 320 us reset framing, correct frame length and immutable active DMA buffer")
    # A HE dimensions request must not index row/column 255.
    reply=m.raw_command(bytes((0xa9,0x42,255,255)))
    assert reply[4]==0 and reply[5:9]==bytes((6,0,16,0)),reply.hex()
    for payload in (bytes((0xa9,0x12,255,0,0,26)),bytes((0xa9,0x12,0,0,0,255)),
                    bytes((0xa9,0x14,0,2,0,4,4,1))):
        assert m.raw_command(payload)[0]==255,payload.hex()
    tests.append("HE dimensions request and malformed/raw unsupported settings are bounded before upstream dispatch")
    result=dict(status="PASS_OFFLINE_NOT_FLASHED",image_sha256=hashlib.sha256(IMAGE).hexdigest(),tests=tests,
        limits=["SPI DMA transfer effects are modeled; real HAL initialization executes", "Physical pin continuity, LED count/order, waveform and host enumeration still need hardware verification"])
    (BUILD/"usb_lighting_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
