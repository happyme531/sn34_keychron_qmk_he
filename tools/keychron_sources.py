"""Prepare patched Keychron modules; retain the historical builder's API."""
from bat68_patches import apply_series
from bat68_build_config import write_if_changed


def prepare_keychron(root, build, qmk):
    prefix = "keyboards/keychron/common/analog_matrix/"
    inputs = [prefix + p.name for p in sorted((qmk / prefix).iterdir()) if p.suffix in (".c", ".h")]
    inputs += ["keyboards/keychron/common/nkro.c", "keyboards/keychron/common/keychron_raw_hid.c", "quantum/via.c"]
    files, record = apply_series(qmk, inputs, build / "vendor/qmk", root / "patches/keychron")
    generated = build / "vendor/keychron_he"
    for relative, path in files.items():
        target = build / "vendor/via.c" if relative == "quantum/via.c" else generated / path.name
        write_if_changed(target, path.read_bytes())
    modules = ("analog_matrix.c", "profile.c", "action_regular_trigger.c", "action_rapid_trigger.c",
               "action_okmc.c", "action_toggle.c", "action_socd.c", "game_controller_common.c")
    sources = [generated / name for name in modules]
    sources += [root / "firmware/keychron" / name for name in ("he.c", "eeprom.c")]
    sources += [qmk / path for path in ("quantum/quantum.c", "quantum/action_tapping.c", "quantum/eeconfig.c",
                "quantum/nvm/eeprom/nvm_eeconfig.c", "quantum/process_keycode/process_quantum.c",
                "quantum/process_keycode/process_default_layer.c")]
    includes = [root / "firmware/keychron", root / "firmware/keychron/platform", generated,
                qmk / "keyboards/keychron/common"]
    return sources, includes, [record]
