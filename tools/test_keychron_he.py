# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute BAT68 ADC -> real Keychron HE -> full QMK quantum -> SDK HID."""
import os
os.environ["BAT68_NATIVE_BUILD"] = "build/keychron_he"
import hashlib
import json
import struct
from test_native_keyboard import Keyboard, KEYS, MAPPING, NAMES
from test_native_usb import BUILD, IMAGE, MANIFEST, SCRATCH, SYMS
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR


class HallKeyboard(Keyboard):
    def __init__(self):
        self.flash_writes = []
        self.fail_page = None
        super().__init__()

    def on_code(self, u, address, size, data):
        if address == (SYMS["sn34_flash_write_eeprom_page"] & ~1):
            from unicorn.arm_const import UC_ARM_REG_R1
            offset = u.reg_read(UC_ARM_REG_R0)
            assert 0x7b000 <= offset < 0x7d000 and offset % 512 == 0
            self.flash_writes.append(offset)
            result = 0
            if self.fail_page == offset:
                result = 0xffffffff
            else:
                u.mem_write(offset, bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1), 512)))
            u.reg_write(UC_ARM_REG_R0, result)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        super().on_code(u, address, size, data)

    def he(self, op, profile=0, row=0, col=0, mode=1, actuation=12, sensitivity=4, release_sensitivity=4):
        return self.command(0x7c, payload=bytes((op, profile, row, col, mode, actuation, sensitivity, release_sensitivity)))

    def travel(self, name, value):
        # Keychron's scaled normalized full stroke is 240, not the old 330.
        self.set(name, (value * 330 + 239) // 240)
        self.step()

    def down(self, usage):
        return usage in self.report()[2:]


def main():
    assert MANIFEST["keychron_he"] and MANIFEST["qmk_commit"] == "2b493ff95f2665db719b1e95c91babb5036e72f3"
    tests = []
    m = HallKeyboard()
    assert m.report() == bytes(8)
    for key in MAPPING:
        if key["name"] == "Fn": continue
        profile = next(k for k in KEYS if k["electrical"] == key["electrical"])
        m.set_key(profile, 160); m.step()
        report = m.report(); usage = int(key["hid_usage"], 0)
        if 0xe0 <= usage <= 0xe7: assert report[0] & (1 << (usage - 0xe0)), (key, report.hex())
        else: assert usage in report[2:], (key, report.hex())
        m.set_key(profile, 0); m.step(); assert m.report() == bytes(8), (key, "stuck")
    tests.append("All 66 regular/modifier keys through actual Keychron raw conversion, regular trigger, QMK quantum and USB HID")
    m.set("Fn", 160); m.set("2", 160); m.step(); assert m.down(0x3b)
    m.release("Fn"); m.release("2"); assert m.report() == bytes(8)
    m.press("Fn", 160); m.press("W", 160); assert m.down(0x52)
    m.release("W"); m.release("Fn"); assert m.report() == bytes(8)
    tests.append("Simultaneous Fn+2 and Fn+W, including release of Fn before the other key")
    for value, pressed in ((60, False), (90, True), (64, True), (44, False)):
        m.travel("W", value); assert m.down(0x1a) == pressed, (value, m.report().hex(), m.he(4, row=2, col=2).hex())
    m.release("W")
    tests.append("Keychron regular trigger actuation and hysteresis")
    assert m.he(1, 1)[2] == 1
    for value, pressed in ((60, False), (130, True), (180, True), (148, False), (170, False), (182, True), (0, False)):
        m.travel("W", value); assert m.down(0x1a) == pressed, ("RT", value, m.report().hex(), m.he(4, row=2, col=2).hex())
    tests.append("Original Keychron rapid-trigger algorithm releases and reactivates around moving extrema")
    assert m.he(1, 0)[2] == 1
    assert m.he(2, 0, 2, 2, 2, 8, 2, 3)[2] == 1
    m.travel("W", 55); assert m.down(0x1a)
    assert m.he(1, 1)[2] == 255
    m.release("W"); assert not m.down(0x1a)
    for kwargs in ({"profile":3},{"row":6},{"col":16},{"mode":3},{"actuation":0},{"sensitivity":40},{"release_sensitivity":0}):
        args = dict(profile=0, row=2, col=2, mode=2, actuation=8, sensitivity=2, release_sensitivity=3)
        args.update(kwargs); assert m.he(2, **args)[2] == 255, args
    tests.append("Per-key HE configuration, released-key guards and invalid setting bounds")
    # Full quantum is linked: MT(MOD_LCTL,KC_A), tap -> A, hold -> Ctrl.
    a = NAMES["A"]; r,c = divmod(a["raw_slot"], 16)
    assert m.command(0x75, 0, r, c, 0x2104)[2] == 2
    m.press("A", 160); assert not m.down(4)
    m.release("A"); assert any(ep == 0x81 and 4 in payload[2:] for ep,payload in m.transfers)
    m.tick += 210; m.step() # Finish the previous tap sequence before testing hold.
    m.press("A", 160); m.tick += 210; m.step(); assert m.report()[0] & 1
    m.release("A"); assert m.report() == bytes(8)
    tests.append("Real QMK action_tapping and quantum process an MT key as tap A and held Ctrl")
    assert m.he(3, 0)[2] == 1
    assert m.flash_writes == list(range(0x7b000,0x7c000,512))
    count = len(m.flash_writes); assert m.he(3,0)[2] == 1 and len(m.flash_writes) == count
    assert m.he(1, 1)[2] == 1
    assert m.he(3, 1)[2] == 1
    assert m.flash_writes[count:] == list(range(0x7c000,0x7d000,512))
    m.call("bat68_eeprom_init"); m.call("analog_matrix_eeconfig_init")
    assert m.he(0)[9] == 1
    assert m.he(1, 0)[2] == 1
    assert m.he(4, 0, 2, 2)[9] == 2
    tests.append("Alternating EEPROM bank save, no-op save, profile index and per-key RT survive cache reload")
    # Interrupt save before its header page: the previously committed bank wins.
    m.fail_page = 0x7be00
    assert m.he(3,0)[2] == 255
    m.call("bat68_eeprom_init"); m.call("analog_matrix_eeconfig_init")
    assert m.he(0)[9] == 1
    tests.append("Interrupted EEPROM save at commit page reloads the previous complete bank")
    assert m.command(0x74)[12] == 7
    result = dict(status="PASS_OFFLINE_NOT_FLASHED", image_sha256=hashlib.sha256(IMAGE).hexdigest(),
                  qmk_commit=MANIFEST["qmk_commit"], tests=tests,
                  limits=["ADC samples and USB hardware modeled; EEPROM page writes modeled at the board wrapper", "Physical RT, power cycle, Flash programming and OTA require hardware validation", "Displacement curve and full-travel values remain estimates"])
    (BUILD/"he_test_results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
