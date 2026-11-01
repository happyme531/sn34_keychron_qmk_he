"""Generate a normalized ADC curve from the documented stock calibration data."""
import json
from build_config import board_directory, write_if_changed


def generate_hall_curve(root, build):
    curve = json.loads((board_directory() / "hall_curve.json").read_text(encoding="utf-8"))
    steps = curve["adc_step_counts"]
    assert len(steps) > 1 and all(step > 0 for step in steps)
    cumulative = [0]
    for step in steps:
        cumulative.append(cumulative[-1] + step)
    normalized = [(value * 65535 + cumulative[-1] // 2) // cumulative[-1] for value in cumulative]
    text = "// Generated from the selected keyboard's hall_curve.json; no stock executable code.\n#pragma once\n"
    text += "static const uint16_t sn34_hall_adc_curve[]={" + ",".join(map(str, normalized)) + "};\n"
    write_if_changed(build / "hall_curve.generated.h",text)
