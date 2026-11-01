"""Generate BAT68 board data shared by all QMK builds."""
import json
from bat68_build_config import write_if_changed
from bat68_model import load_board


def generate_board(ROOT, BUILD):
    model=load_board(ROOT/"firmware/board/bat68.json")
    mapping=model["keys"];roles=model["roles"];unit=model["layout_unit"]
    layers={layer["role"]:layer["id"] for layer in model["layers"]}
    rows_count,cols=model["matrix"]["rows"],model["matrix"]["cols"]
    layer_count=len(model["layers"])
    bases=(layers["win_base"],layers["mac_base"])
    functions=(layers["win_fn"],layers["mac_fn"])
    by_raw={k["raw_slot"]:k for k in mapping}
    config="// Generated from firmware/board/bat68.json.\n#pragma once\n"
    constants={"MATRIX_ROWS":rows_count,"MATRIX_COLS":cols,"BAT68_KEY_COUNT":len(mapping),
               "RGB_MATRIX_LED_COUNT":len(mapping),"DYNAMIC_KEYMAP_LAYER_COUNT":layer_count,
               "BAT68_MATRIX_ABI_VERSION":model["matrix"]["abi_version"]}
    constants.update({"BAT68_"+role.upper()+"_LAYER":index for role,index in layers.items()})
    for role,prefix in (("profile_trigger","PROF_TRIG"),("profile_1","PROF_1"),("profile_2","PROF_2"),("profile_3","PROF_3")):
        row,col=by_raw[roles[role]]["matrix"]
        constants[prefix+"_KEY_ROW"]=row;constants[prefix+"_KEY_COL"]=col
    constants.update(VENDOR_ID=int(model["usb"]["vid"],0),PRODUCT_ID=int(model["usb"]["pid"],0),
                     DEVICE_VER=int(model["usb"]["bcd_device"],0))
    config+="".join(f"#define {name} {value}\n" for name,value in constants.items())
    config+='#define BAT68_MATRIX_ABI_SHA256 "'+model["matrix"]["abi_sha256"]+'"\n'
    config+="#define BAT68_FN_LAYER_MASK ((1u << BAT68_WIN_FN_LAYER) | (1u << BAT68_MAC_FN_LAYER))\n"
    write_if_changed(BUILD/"board_config.generated.h",config)
    overrides=json.loads((ROOT/"firmware/board/keymap_overrides.json").read_text(encoding="utf-8"))
    keymaps=[[["KC_NO"]*cols for _ in range(rows_count)] for _ in range(layer_count)]
    for l in functions:keymaps[l]=[["KC_TRNS"]*cols for _ in range(rows_count)]
    board='#pragma once\n#include "board_config.generated.h"\ntypedef struct {uint8_t raw_slot,matrix_slot,electrical;} board_key_t;\nstatic const board_key_t board_keys[]={\n'
    hall=f"#pragma once\n#define BAT68_HALL_KEYS {len(mapping)}\ntypedef struct {{uint8_t slot,electrical;uint16_t idle,bottom;}} bat68_hall_key_t;\nstatic const bat68_hall_key_t hall_keys[]={{\n"
    for k in mapping:
        raw=k["raw_slot"];r,c=k["matrix"];slot=r*cols+c
        p=k["hall"]
        board+=f"{{{raw},{slot},{k['electrical']}}},\n"
        hall+=f"{{{slot},{k['electrical']},{p['released']},{p['bottom']}}},\n"
        for l,fn in zip(bases,functions):keymaps[l][r][c]=f"MO({fn})" if raw==roles["fn"] else k["hid_usage"]
        # macOS places Option left of Command. Keep physical key positions,
        # but swap left Alt/GUI on the Mac base layer.
        if raw==roles["win"]:keymaps[layers["mac_base"]][r][c]="KC_LALT"
        if raw==roles["left_alt"]:keymaps[layers["mac_base"]][r][c]="KC_LGUI"
        for l in functions:keymaps[l][r][c]=overrides.get("1",{}).get(k["name"],"KC_TRNS")
    write_if_changed(BUILD/"board.generated.h",board+"};\n")
    write_if_changed(BUILD/"hall.generated.h",hall+"};\n")
    header=f"#pragma once\nconst uint16_t PROGMEM keymaps[{layer_count}][MATRIX_ROWS][MATRIX_COLS]={{\n"
    for layer in keymaps:header+="{\n"+"\n".join("{"+",".join(row)+"}," for row in layer)+"\n},\n"
    write_if_changed(BUILD/"keymap.generated.h",header+"};\n")
    write_if_changed(BUILD/"board.json",json.dumps(mapping,indent=2))
    physical=sorted(mapping,key=lambda k:(k["rect"][1],k["rect"][0]))
    matrix=[[255]*cols for _ in range(rows_count)];points=[None]*len(mapping);flags=[4]*len(mapping)
    maxx=max(k["rect"][0]+k["rect"][2] for k in physical);maxy=max(k["rect"][1]+k["rect"][3] for k in physical)
    for k in physical:
        led=k["led"]
        r,c=k["matrix"];matrix[r][c]=led;x,y,w,h=k["rect"]
        if k["raw_slot"]==roles["fn"] or 0xe0<=int(k["hid_usage"],0)<=0xe7:flags[led]|=1
        points[led]=[round((x+w/2)*224/maxx),round((y+h/2)*64/maxy)]
    rgb='#pragma once\nled_config_t g_led_config={\n{'+','.join('{'+','.join(map(str,row))+'}' for row in matrix)+'},\n'
    rgb+='{'+','.join('{'+','.join(map(str,p))+'}' for p in points)+'},\n{'+','.join(map(str,flags))+'}\n};\n'
    write_if_changed(BUILD/"rgb.generated.h",rgb)
    rows=[]
    for y in sorted({k["rect"][1] for k in physical}):
        row=[];cursor=0
        for k in (k for k in physical if k["rect"][1]==y):
            x,_,w,h=k["rect"];position=x/unit;config={}
            if abs(position-cursor)>0.02:config["x"]=round(position-cursor,3)
            width=round((w+4)/unit,3)
            if abs(width-1)>0.02:config["w"]=width
            if config:row.append(config)
            r,c=k["matrix"];row.append(f"{r},{c}");cursor=position+width
        rows.append(row)
    via=dict(name=model["name"],vendorId=f"0x{constants['VENDOR_ID']:04X}",productId=f"0x{constants['PRODUCT_ID']:04X}",matrix=dict(rows=rows_count,cols=cols),
             layouts=dict(keymap=rows),menus=["qmk_rgb_matrix"],keycodes=["qmk_lighting"])
    write_if_changed(BUILD/"bat68_via.json",json.dumps(via,indent=2))
    # Keep the proven dummy channel-11 conversion, followed by the original
    # final-sample order, but omit channels with no switch in this mux phase.
    used={key["raw_slot"] for key in mapping}
    channels=((10,11,12,13),(1,2,3,4),(5,6,7,14))
    order=(10,2,1,4,3,6,5,14,7,13,12,11)
    sequences=[];covered=[]
    for phase in range(8):
        upper=phase>>2;pair=(phase&3)*2
        live={channels[group][lane^upper]:group*32+upper*16+(lane>>1)*8+pair+(lane&1)
              for group in range(3) for lane in range(4)
              if group*32+upper*16+(lane>>1)*8+pair+(lane&1) in used}
        covered.extend(live.values())
        sequences.append([11]+[channel for channel in order if channel in live])
    assert len(covered)==len(set(covered))==len(mapping) and set(covered)==used
    scan="// Generated from the validated 67-switch board map.\n#pragma once\n"
    scan+="static const uint8_t bat68_adc_phase_count[]={"+",".join(str(len(seq)) for seq in sequences)+"};\n"
    scan+="static const uint32_t bat68_adc_phase_sequence[8][3]={\n"
    for seq in sequences:
        assert 1<=len(seq)<=12
        padded=seq+[0]*(12-len(seq))
        words=[sum(padded[i+j]<<(j*8) for j in range(4)) for i in range(0,12,4)]
        scan+="{"+",".join(hex(word)+"u" for word in words)+"},\n"
    write_if_changed(BUILD/"scan.generated.h",scan+"};\n")

