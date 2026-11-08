"""Exercise BOOM68's real Launcher protocol, zone rendering and persistence."""
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
from emulator import BUILD, FIRMWARE, IMAGE, SYMS, SCRATCH
from keyboard import Keyboard, NAMES
from storage import LAYOUT
from export import definitions


def rgb(m, command, *payload):
    return m.raw_command(bytes((0xa8, command, *payload)))


def get_regions(m):
    return b''.join(rgb(m, 12, start, min(29, 94-start))[3:3+min(29, 94-start)]
                    for start in range(0, 94, 29))


def set_effects(m, zone, entries):
    payload = b''.join(struct.pack('<4BI', *entry) for entry in entries)
    return rgb(m, 15, zone, 0, len(entries), *payload)


def settle(m):
    for _ in range(160):
        m.step(2)


def pixel(m, index):
    # Inspect a completed DMA frame, not the partially rendered working buffer.
    encoded = m.spi[-1][120 + index * 12:132 + index * 12]
    lookup = {0x88: 0, 0x8e: 1, 0xe8: 2, 0xee: 3}
    grb = [sum(lookup[encoded[channel * 4 + part]] << (6 - part * 2) for part in range(4))
           for channel in range(3)]
    return grb[1], grb[0], grb[2]


def main():
    m = Keyboard()
    assert m.raw_command(b'\xa2')[2] & 0x80, 'Advertise custom RGB to Launcher'
    assert rgb(m, 1)[2:5] == bytes((0, 1, 0))
    assert rgb(m, 5)[2:4] == bytes((0, 94))
    assert rgb(m, 11)[2:5] == bytes((0, 2, 5))
    expected = bytes(67) + bytes((1,)) * 27
    assert get_regions(m) == expected, 'All 27 strip LEDs default to zone 2'
    for zone, wire in ((0, 5), (1, 2)):
        assert rgb(m, 14, zone, 0, 1)[2:7] == bytes((0, wire, 0, 255, 127))
    via, launcher = definitions(FIRMWARE, 'langtu/boom68/wired')
    effects = dict((item['name'], item['wire']) for item in FIRMWARE.rgb_protocol)
    assert effects['PER_KEY_RGB'] == 23 and effects['MIXED_RGB'] == 24
    assert any(option == ['Mixed Rgb', 24] for option in via['menus'][0]['content'][0]['content'][1]['options'])

    # IDs within the list need the same translation as the outer VIA mode.
    for effect in FIRMWARE.rgb_protocol:
        if effect['wire'] == 24:
            continue  # Nested Mix RGB would recurse.
        entry = (effect['wire'], 31, 210, 93, 5000)
        assert set_effects(m, 0, [entry])[2] == 0, effect
        assert rgb(m, 14, 0, 0, 1)[3:11] == struct.pack('<4BI', *entry), effect
    entries = [(1, 0, 255, 100, 5000), (2, 85, 220, 120, 6000), (5, 170, 200, 140, 7000)]
    assert set_effects(m, 0, entries)[2] == 0
    assert rgb(m, 14, 0, 0, 3)[3:27] == b''.join(struct.pack('<4BI', *entry) for entry in entries)

    # Reject complete malformed writes before any list/color/region mutation.
    before = bytes(m.u.mem_read(SYMS['effect_list'], 80))
    for zone, start, count in ((2, 0, 1), (255, 0, 1), (0, 5, 1), (0, 4, 2), (0, 0, 4)):
        assert rgb(m, 14, zone, start, count)[2] == 1
        assert rgb(m, 15, zone, start, count)[2] == 1
    for bad in (24, 51, 255):
        assert set_effects(m, 0, [(1, 0, 255, 127, 5000), (bad, 0, 255, 127, 5000)])[2] == 1
        assert bytes(m.u.mem_read(SYMS['effect_list'], 80)) == before
    for start, count in ((94, 1), (93, 2), (255, 1), (0, 10)):
        assert rgb(m, 9, start, count)[2] == 1
        assert rgb(m, 10, start, count)[2] == 1
    assert rgb(m, 6, 6, 1, 0, 0)[2] == 1
    assert rgb(m, 13, 93, 2, 0, 1)[2] == 1
    assert rgb(m, 13, 0, 1, 2)[2] == 1
    assert get_regions(m) == expected

    # Real frame rendering must cover keys and unbound strip pixels separately.
    assert set_effects(m, 0, [(1, 0, 255, 127, 5000), (0, 0, 0, 0, 0), (0, 0, 0, 0, 0)])[2] == 0
    assert set_effects(m, 1, [(1, 85, 255, 127, 5000)])[2] == 0
    assert m.raw_command(bytes((7, 3, 2, 24)))[0] == 7
    assert m.raw_command(bytes((8, 3, 2)))[3] == 24
    settle(m)
    red, green = pixel(m, 0), pixel(m, 80)
    assert red[0] > 0 and red[1:] == (0, 0), red
    assert green[1] > 0 and green[0] == green[2] == 0, green
    assert pixel(m, 66) == red and pixel(m, 67) == pixel(m, 93) == green
    assert rgb(m, 13, 80, 1, 0)[2] == 0
    settle(m)
    assert pixel(m, 80) == red, 'An unbound strip LED can change zones by LED ID'
    assert rgb(m, 13, 80, 1, 1)[2] == 0

    # Status indicators still overlay only their own pixels.
    m.call('default_layer_set', 1 << 2)
    settle(m)
    assert pixel(m, 68)[0] == pixel(m, 68)[1] == pixel(m, 68)[2] > 0, pixel(m, 68)
    assert pixel(m, 80) == green
    m.call('default_layer_set', 1)

    # Per-key RGB accepts arbitrary LED IDs, including the end of the strip.
    assert rgb(m, 10, 93, 1, 170, 255, 255)[2] == 0
    assert rgb(m, 9, 93, 1)[3:6] == bytes((170, 255, 255))
    assert rgb(m, 8, 0)[2] == 0
    m.raw_command(bytes((7, 3, 2, 23)))
    settle(m)
    blue = pixel(m, 93)
    assert blue[2] > 0 and blue[:2] == (0, 0), blue

    # Restore Mix, save through the public command, then boot a fresh instance.
    m.raw_command(bytes((7, 3, 2, 24)))
    assert rgb(m, 2)[2] == 0
    m.raw_command(bytes((9, 3)))
    m.remap('A', 5)
    m.u.mem_write(SCRATCH, b'macro\0')
    m.call('dynamic_keymap_macro_set_buffer', 0, 6, SCRATCH)
    r, c = NAMES['A']['matrix']
    calibration = m.raw_command(bytes((0xa9, 0x42, r, c)))[5:9]
    assert m.save() != 0xffffffff
    restored = Keyboard(bytes(m.u.mem_read(LAYOUT.code_limit, LAYOUT.app_size - LAYOUT.code_limit)))
    assert get_regions(restored) == expected
    assert restored.raw_command(bytes((8, 3, 2)))[3] == 24
    assert rgb(restored, 14, 1, 0, 1)[3:11] == struct.pack('<4BI', 1, 85, 255, 127, 5000)
    assert rgb(restored, 9, 93, 1)[3:6] == bytes((170, 255, 255))
    assert restored.call('dynamic_keymap_get_keycode', 0, r, c) == 5
    assert restored.raw_command(bytes((0xa9, 0x42, r, c)))[5:9] == calibration
    restored.call('dynamic_keymap_macro_get_buffer', 0, 6, SCRATCH)
    assert bytes(restored.u.mem_read(SCRATCH, 6)) == b'macro\0'
    settle(restored)
    assert pixel(restored, 0) == red and pixel(restored, 80) == green

    # A zone advances its own timeline while the other zone stays green.
    assert set_effects(restored, 0, [(1, 0, 255, 127, 2000), (1, 170, 255, 127, 2000)])[2] == 0
    settle(restored)
    assert pixel(restored, 0)[0] > 0 and pixel(restored, 0)[2] == 0
    restored.step(1900)
    settle(restored)
    assert pixel(restored, 0)[2] > 0 and pixel(restored, 0)[0] == 0
    assert pixel(restored, 80) == green

    # Leaving a custom mode must restore full-board ordinary effects.
    restored.raw_command(bytes((7, 3, 2, 1)))
    settle(restored)
    assert pixel(restored, 0) == pixel(restored, 80)

    # First enabling RGB on a v5 board initialized without it populates only
    # the reserved RGB block, preserving the existing HE/VIA configuration.
    restored.u.mem_write(SCRATCH, bytes(LAYOUT.custom_rgb_size))
    restored.call('eeprom_update_block', SCRATCH, LAYOUT.eeprom_base + LAYOUT.he['size'], LAYOUT.custom_rgb_size)
    assert restored.save() != 0xffffffff
    enabled = Keyboard(bytes(restored.u.mem_read(LAYOUT.code_limit, LAYOUT.app_size - LAYOUT.code_limit)))
    assert get_regions(enabled) == expected
    assert enabled.call('dynamic_keymap_get_keycode', 0, r, c) == 5
    assert enabled.raw_command(bytes((0xa9, 0x42, r, c)))[5:9] == calibration
    enabled.call('dynamic_keymap_macro_get_buffer', 0, 6, SCRATCH)
    assert bytes(enabled.u.mem_read(SCRATCH, 6)) == b'macro\0'
    result = dict(status='PASS_OFFLINE_NOT_FLASHED', image_sha256=hashlib.sha256(IMAGE).hexdigest(),
                  tests=['Launcher capability, LED count, two zones and five slots',
                         'Default 67 key LEDs in zone 1 and all 27 strip LEDs in zone 2',
                         'All supported effect IDs round-trip, including multi-entry lists',
                         'Invalid regions, effects, rows and color ranges reject without partial writes',
                         'Distinct colors rendered on keys and strip; arbitrary strip LED can change zones',
                         'Independent zone timeline advances while the other zone holds its color',
                         'Layer indicators overlay the strip and ordinary modes restore full-board output',
                         'Per-LED colors, zone lists, macros, remaps and calibration survive save/reboot',
                         'An empty reserved RGB block initializes without resetting HE, remaps or macros'])
    (BUILD / 'custom_rgb_results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
