"""Generate per-target tables; no keyboard wiring or keymap policy lives here."""
import json
from build_config import board_directory, write_if_changed
from model import load_board


def generate_board(root, build, model_path=None):
    model = load_board(model_path or board_directory() / "board.json")
    mapping, roles = model["keys"], model.get("roles", {})
    matrix, scan = model["matrix"], model["scan"]
    rows_count, cols = matrix["rows"], matrix["cols"]
    layers = {layer["role"]: layer["id"] for layer in model["layers"]}
    by_raw = {k["raw_slot"]: k for k in mapping}
    constants = {"MATRIX_ROWS": rows_count, "MATRIX_COLS": cols, "SN34_KEY_COUNT": len(mapping),
                 "RGB_MATRIX_LED_COUNT": model["leds"]["count"], "DYNAMIC_KEYMAP_LAYER_COUNT": len(model["layers"]),
                 "SN34_MATRIX_ABI_VERSION": matrix["abi_version"], "SN34_SAMPLE_COUNT": scan["sample_count"],
                 "SN34_MUX_PHASES": len(scan["phases"])}
    constants.update({"SN34_" + role.upper() + "_LAYER": index for role, index in layers.items()})
    for role, prefix in (("profile_trigger", "PROF_TRIG"), ("profile_1", "PROF_1"), ("profile_2", "PROF_2"), ("profile_3", "PROF_3")):
        row, col = by_raw[roles[role]]["matrix"] if role in roles else (255, 255)
        constants[prefix + "_KEY_ROW"], constants[prefix + "_KEY_COL"] = row, col
    constants.update(VENDOR_ID=int(model["usb"]["vid"], 0), PRODUCT_ID=int(model["usb"]["pid"], 0),
                     DEVICE_VER=int(model["usb"]["bcd_device"], 0))
    config = "// Generated from the selected keyboard board model.\n#pragma once\n"
    config += "".join(f"#define {name} {value}\n" for name, value in constants.items())
    config += '#define SN34_MATRIX_ABI_SHA256 "' + matrix["abi_sha256"] + '"\n'
    mask = sum(1 << layer["id"] for layer in model["layers"] if layer.get("role", "").endswith("_fn") or layer.get("fn", False))
    config += f"#define SN34_FN_LAYER_MASK {mask}u\n"
    for field in ("manufacturer", "product", "serial", "diagnostic_tag"):
        config += "#define SN34_USB_" + field.upper() + " " + json.dumps(model["usb"][field]) + "\n"
    config += f"#define SN34_CLOCK_HZ {model['hardware']['clock_hz']}u\n"
    write_if_changed(build / "board_config.generated.h", config)
    board = '#pragma once\n#include "board_config.generated.h"\ntypedef struct {uint16_t raw_slot,matrix_slot,electrical;} board_key_t;\nstatic const board_key_t board_keys[]={\n'
    hall = f"#pragma once\n#define SN34_HALL_KEYS {len(mapping)}\ntypedef struct {{uint16_t slot,electrical;uint16_t idle,bottom;}} sn34_hall_key_t;\nstatic const sn34_hall_key_t hall_keys[]={{\n"
    for key in mapping:
        r, c = key["matrix"]
        board += f"{{{key['raw_slot']},{r*cols+c},{key['electrical']}}},\n"
        hall += f"{{{r*cols+c},{key['electrical']},{key['hall']['released']},{key['hall']['bottom']}}},\n"
    write_if_changed(build / "board.generated.h", board + "};\n")
    write_if_changed(build / "hall.generated.h", hall + "};\n")
    keymap = f"#pragma once\nconst uint16_t PROGMEM keymaps[{len(model['layers'])}][MATRIX_ROWS][MATRIX_COLS]={{\n"
    for layer in model["layers"]:
        default = {"physical": "KC_NO", "transparent": "KC_TRNS", "none": "KC_NO"}[layer["default"]]
        table = [[default] * cols for _ in range(rows_count)]
        for key in mapping:
            r, c = key["matrix"]
            table[r][c] = layer.get("overrides", {}).get(str(key["raw_slot"]),
                            key["hid_usage"] if layer["default"] == "physical" else default)
        keymap += "{\n" + "\n".join("{" + ",".join(row) + "}," for row in table) + "\n},\n"
    write_if_changed(build / "keymap.generated.h", keymap + "};\n")
    write_if_changed(build / "board.json", json.dumps(mapping, indent=2))
    generate_leds(model, build)
    generate_via(model, build)
    generate_scan(model, build)


def generate_leds(model, build):
    mapping, cols, rows = model["keys"], model["matrix"]["cols"], model["matrix"]["rows"]
    count = model["leds"]["count"]
    matrix = [[255] * cols for _ in range(rows)]
    points, flags = [None] * count, [4] * count
    maxx = max(k["rect"][0] + k["rect"][2] for k in mapping)
    maxy = max(k["rect"][1] + k["rect"][3] for k in mapping)
    for key in mapping:
        if key.get("led") is None:
            continue
        led = key["led"]
        r, c = key["matrix"]
        matrix[r][c] = led
        x, y, w, h = key["rect"]
        points[led] = [round((x+w/2)*224/maxx), round((y+h/2)*64/maxy)]
        if key["raw_slot"] == model.get("roles", {}).get("fn") or 0xe0 <= int(key["hid_usage"], 0) <= 0xe7:
            flags[led] |= 1
    for led in model["leds"].get("extra", []):
        points[led["index"]], flags[led["index"]] = led["point"], led.get("flags", 2)
    rgb = '#pragma once\nled_config_t g_led_config={\n{' + ','.join('{'+','.join(map(str,row))+'}' for row in matrix) + '},\n'
    rgb += '{' + ','.join('{'+','.join(map(str,p))+'}' for p in points) + '},\n{' + ','.join(map(str,flags)) + '}\n};\n'
    write_if_changed(build / "rgb.generated.h", rgb)


def generate_via(model, build):
    rows, unit = [], model["layout_unit"]
    physical = sorted(model["keys"], key=lambda k:(k["rect"][1], k["rect"][0]))
    for y in sorted({k["rect"][1] for k in physical}):
        row, cursor = [], 0
        for key in (k for k in physical if k["rect"][1] == y):
            x, _, w, h = key["rect"]
            position, config = x/unit, {}
            if abs(position-cursor) > 0.02: config["x"] = round(position-cursor, 3)
            width = round((w+4)/unit, 3)
            if abs(width-1) > 0.02: config["w"] = width
            if config: row.append(config)
            r,c = key["matrix"]
            row.append(f"{r},{c}")
            cursor = position+width
        rows.append(row)
    via = dict(name=model["name"], vendorId=model["usb"]["vid"], productId=model["usb"]["pid"],
               matrix=dict(rows=model["matrix"]["rows"], cols=model["matrix"]["cols"]),
               layouts=dict(keymap=rows), menus=["qmk_rgb_matrix"], keycodes=["qmk_lighting"])
    write_if_changed(build / "sn34_via.json", json.dumps(via, indent=2))


def generate_scan(model, build):
    scan = model["scan"]
    used = {key["raw_slot"] for key in model["keys"]}
    counts, packed = [], []
    text = "// Generated ADC ranks and scatter; each target owns its wiring.\n#pragma once\n"
    for phase in scan["phases"]:
        live = {s["channel"] for s in phase["samples"] if s["slot"] in used}
        sequence = phase.get("presample", []) + [ch for ch in scan["channel_order"] if ch in live]
        if not 1 <= len(sequence) <= 16: raise ValueError("ADC scan needs 1..16 ranks")
        counts.append(len(sequence))
        sequence += [0] * (16-len(sequence))
        packed.append([sum(sequence[i+j] << (j*8) for j in range(4)) for i in range(0,16,4)])
    text += "static const uint8_t sn34_adc_phase_count[]={" + ",".join(map(str,counts)) + "};\n"
    text += "static const uint32_t sn34_adc_phase_sequence[][4]={\n"
    text += "".join("{"+",".join(hex(v)+"u" for v in row)+"},\n" for row in packed) + "};\n"
    text += "static inline void sn34_scatter_adc_phase(uint16_t *raw,const uint16_t *adc,unsigned phase){switch(phase){\n"
    for index, phase in enumerate(scan["phases"]):
        text += f"case {index}:\n" + "".join(f"raw[{s['slot']}]=adc[{s['channel']}];" for s in phase["samples"]) + "break;\n"
    text += "}}\n"
    text += "#define SN34_ADC_INITIAL_SEQUENCE {" + ",".join(map(str,scan["initial_sequence"])) + "}\n"
    text += "#define SN34_ADC_COMPACT_SEQUENCE {" + ",".join(map(str,scan["compact_sequence"])) + "}\n"
    write_if_changed(build / "scan.generated.h", text)

