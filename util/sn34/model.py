"""Board identity and validation; electrical wiring is supplied by each target."""
import hashlib
import json
from build_config import ROOT, board_directory, keyboard_name, write_if_changed

BOARD_FILE = board_directory() / "board.json"


def matrix_digest(keys):
    coordinates = sorted([[k["raw_slot"], *k["matrix"]] for k in keys])
    return hashlib.sha256(json.dumps(coordinates, separators=(",", ":")).encode()).hexdigest()


def load_board(path=None):
    board = json.loads((path or board_directory() / "board.json").read_text(encoding="utf-8"))
    keys, matrix, scan = board["keys"], board["matrix"], board["scan"]
    if not keys or not 1<=matrix['rows']<=255 or not 1<=matrix['cols']<=32:
        raise ValueError('Invalid QMK matrix dimensions or empty key set')
    if not 1<=len(board['layers'])<=8:
        raise ValueError('The selected layer-state backend supports 1..8 layers')
    if board["schema_version"] != 1 or matrix_digest(keys) != matrix["abi_sha256"]:
        raise ValueError("Board schema or matrix ABI digest changed; review the configuration migration")
    for field in ("raw_slot", "electrical", "layout_index"):
        if len({k[field] for k in keys}) != len(keys):
            raise ValueError(f"Duplicate board {field}")
    if len({tuple(k["matrix"]) for k in keys}) != len(keys):
        raise ValueError("Duplicate QMK matrix coordinate")
    led_ids = [k["led"] for k in keys if k.get("led") is not None]
    led_ids += [led["index"] for led in board["leds"].get("extra", [])]
    if sorted(led_ids) != list(range(board["leds"]["count"])):
        raise ValueError("LED indices must cover the configured chain exactly once")
    slots = set()
    for phase in scan["phases"]:
        channels = set()
        for sample in phase["samples"]:
            if not 0 <= sample["slot"] < scan["sample_count"] or not 0 <= sample["channel"] < 18:
                raise ValueError("Invalid ADC sample mapping")
            if sample["slot"] in slots or sample["channel"] in channels:
                raise ValueError("Duplicate scan slot/channel")
            slots.add(sample["slot"])
            channels.add(sample["channel"])
    for key in keys:
        row, col = key["matrix"]
        if not (0 <= row < matrix["rows"] and 0 <= col < matrix["cols"] and key["raw_slot"] in slots):
            raise ValueError(f"Invalid matrix/raw coordinate: {key['raw_slot']}")
        if key["hall"]["released"] <= key["hall"]["bottom"]:
            raise ValueError("Invalid Hall default endpoints")
    if not set(board.get("roles", {}).values()) <= {k["raw_slot"] for k in keys}:
        raise ValueError("Board role refers to a missing physical key")
    if [layer["id"] for layer in board["layers"]] != list(range(len(board["layers"]))):
        raise ValueError("Layer IDs must be ordered and contiguous")
    if len(scan["phases"]) > 1 << len(scan["mux_pins"]) or not scan["phases"]:
        raise ValueError("MUX pins cannot select every configured phase")
    return board


def keyboard_definition(board, target=None):
    target = target or json.loads((board_directory() / "target.json").read_text(encoding="utf-8"))
    unit = board["layout_unit"]
    keys = sorted(board["keys"], key=lambda k: (k["rect"][1], k["rect"][0]))
    top = min(k["rect"][1] for k in keys)
    layout = [{"label": k["name"], "matrix": k["matrix"], "x": round(k["rect"][0] / unit, 3),
               "y": round((k["rect"][1] - top) / unit, 3), "w": round((k["rect"][2] + 4) / unit, 3)} for k in keys]
    return {"keyboard_name": board["name"], "manufacturer": board["manufacturer"], "maintainer": "SN34",
            "processor": target["mcu"], "bootloader": "custom",
            "usb": {"vid": f"0x{int(board['usb']['vid'], 0):04X}", "pid": f"0x{int(board['usb']['pid'], 0):04X}",
                    "device_version": board["usb"]["device_version"]}, "layouts": {"LAYOUT": {"layout": layout}}}


def sync_keyboard_definition(qmk=ROOT, board=None, check=False):
    board = board or load_board()
    expected = keyboard_definition(board)
    target=json.loads((board_directory()/'target.json').read_text(encoding='utf-8'))
    path = qmk / "keyboards" / keyboard_name() / "keyboard.json"
    header = ('// Generated from this keyboard\'s board/board.json.\n#pragma once\n'
              '#define MATRIX_ROWS ' + str(board["matrix"]["rows"]) + '\n#define MATRIX_COLS ' +
              str(board["matrix"]["cols"]) + '\n#include "' + target.get('config','config_base.h') + '"\n')
    config = path.with_name("config.h")
    if check:
        if json.loads(path.read_text(encoding="utf-8")) != expected or config.read_text(encoding="utf-8") != header:
            raise ValueError("Generated keyboard metadata is stale; run util/sn34/build.py --prepare-only")
    else:
        write_if_changed(path, json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
        write_if_changed(config, header)

