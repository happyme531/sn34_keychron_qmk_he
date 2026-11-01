"""Canonical board identities, mappings and QMK keyboard metadata."""
import hashlib
import json
from bat68_build_config import ROOT, write_if_changed

BOARD_FILE = ROOT / "firmware/board/bat68.json"


def matrix_digest(keys):
    coordinates = sorted([[k["raw_slot"], *k["matrix"]] for k in keys])
    return hashlib.sha256(json.dumps(coordinates, separators=(",", ":")).encode()).hexdigest()


def load_board(path=BOARD_FILE):
    board = json.loads(path.read_text(encoding="utf-8"))
    keys, matrix = board["keys"], board["matrix"]
    if board["schema_version"] != 1 or matrix_digest(keys) != matrix["abi_sha256"]:
        raise ValueError("Board schema or matrix ABI digest changed; review the configuration migration")
    for field in ("raw_slot", "electrical", "layout_index", "led"):
        if len({k[field] for k in keys}) != len(keys):
            raise ValueError(f"Duplicate board {field}")
    if len({tuple(k["matrix"]) for k in keys}) != len(keys):
        raise ValueError("Duplicate QMK matrix coordinate")
    if {k["led"] for k in keys} != set(range(len(keys))):
        raise ValueError("LED order must be a permutation of physical keys")
    for key in keys:
        row, col = key["matrix"]
        if not (0 <= row < matrix["rows"] and 0 <= col < matrix["cols"] and 0 <= key["raw_slot"] < 96):
            raise ValueError(f"Invalid matrix/raw coordinate: {key['raw_slot']}")
        electrical = key["electrical"]
        if (electrical & 7) * 16 + (electrical >> 3) != key["raw_slot"]:
            raise ValueError("Electrical identity no longer matches board wiring")
        if key["hall"]["released"] <= key["hall"]["bottom"]:
            raise ValueError("Invalid Hall default endpoints")
    slots = {k["raw_slot"] for k in keys}
    if not set(board["roles"].values()) <= slots:
        raise ValueError("Board role refers to a missing physical key")
    if [layer["id"] for layer in board["layers"]] != list(range(len(board["layers"]))):
        raise ValueError("Layer IDs must be ordered and contiguous")
    return board


def keyboard_definition(board):
    unit = board["layout_unit"]
    keys = sorted(board["keys"], key=lambda k: (k["rect"][1], k["rect"][0]))
    top = min(k["rect"][1] for k in keys)
    layout = [{"label": k["name"], "matrix": k["matrix"],
               "x": round(k["rect"][0] / unit, 3), "y": round((k["rect"][1] - top) / unit, 3),
               "w": round((k["rect"][2] + 4) / unit, 3)} for k in keys]
    return {"keyboard_name": board["name"], "manufacturer": board["manufacturer"], "maintainer": "BAT68",
            "processor": "SN34F280", "bootloader": "custom",
            "usb": {"vid": f"0x{int(board['usb']['vid'], 0):04X}",
                    "pid": f"0x{int(board['usb']['pid'], 0):04X}", "device_version": board["usb"]["device_version"]},
            "layouts": {"LAYOUT": {"layout": layout}}}


def sync_keyboard_definition(qmk, board=None, check=False):
    board = board or load_board()
    expected = keyboard_definition(board)
    path = qmk / "keyboards/battle68/keyboard.json"
    # QMK's metadata parser reads literal matrix dimensions from config.h;
    # it does not follow the generated runtime include. Both are derived here.
    header = ('// Generated from firmware/board/bat68.json; edit the model instead.\n'
              '#pragma once\n#define MATRIX_ROWS ' + str(board["matrix"]["rows"]) +
              '\n#define MATRIX_COLS ' + str(board["matrix"]["cols"]) + '\n#include "qmk/config.h"\n')
    config = path.with_name("config.h")
    if check:
        if json.loads(path.read_text(encoding="utf-8")) != expected or config.read_text(encoding="utf-8") != header:
            raise ValueError("Generated keyboard metadata is stale; run tools/build_bat68.py to synchronize it")
    else:
        write_if_changed(path, json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
        write_if_changed(config, header)
