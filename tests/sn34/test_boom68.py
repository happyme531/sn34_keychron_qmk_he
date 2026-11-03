"""Run BOOM68 bank selection, Hall keys, digital button, encoder and RGB offline."""
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent/'common'))
from emulator import Machine, BUILD, IMAGE, SYMS, SCRATCH
from keyboard import Keyboard, KEYS, NAMES
from model import load_board
from storage import LAYOUT
from test_native_scan import Peripheral
from unicorn import UC_HOOK_MEM_READ
from emulator import FIRMWARE
from export import definitions

GPIO3 = 0x4003a000
ADC = 0x40027000


class BoomPeripheral(Peripheral):
    def __init__(self):
        self.events = []
        self.cycles = 0
        self.selected_at = 0
        super().__init__()

    def read(self, u, offset, size, data):
        address = 0x40000000 + offset
        if address in (GPIO3+0x10, GPIO3+0x14):return 0
        if ADC <= address < ADC+64:
            self.events.append(('adc', address, self.regs.get(0x40037000, 0), self.regs.get(GPIO3, 0)))
        return super().read(u, offset, size, data)

    def write(self, u, offset, size, value, data):
        address = 0x40000000 + offset
        self.events.append(('write', address, value))
        if (address == 0x40037014 and value & 0xf800) or (address == GPIO3+0x14 and value & 3):
            self.selected_at = self.cycles
        if address == ADC+0x100 and value & 0x10:
            assert self.cycles - self.selected_at >= 8 * 192, 'ADC started before the sensor bank settled'
        if address == GPIO3+0x10:
            self.regs[GPIO3] = self.regs.get(GPIO3, 0) | value
        elif address == GPIO3+0x14:
            self.regs[GPIO3] = self.regs.get(GPIO3, 0) & ~value
        else:super().write(u, offset, size, value, data)


class Scanner(Machine):
    def __init__(self):
        super().__init__()
        self.hw = BoomPeripheral()
        self.u.mem_unmap(0x40000000, 0x100000)
        self.u.mmio_map(0x40000000, 0x100000, self.hw.read, None, self.hw.write, None)
        self.u.mem_map(0xe000e000, 0x1000)
        self.u.mem_map(0xe0001000, 0x1000)
        def advance_clock(u, access, address, size, value, data):
            self.hw.cycles += 64
            u.mem_write(address, struct.pack('<I', self.hw.cycles & 0xffffffff))
        self.u.hook_add(UC_HOOK_MEM_READ, advance_clock, begin=0xe0001004, end=0xe0001007)
        self.call('native_board_init')
        assert self.call('native_scan_init') == 0

    def interrupt(self, values):
        self.hw.channels = values.copy()
        self.hw.regs[ADC+0x10c] = 1
        self.hw.events.clear()
        self.call('ADC0_IRQHandler')


def scanner_test():
    m = Scanner()
    model = load_board()
    assert ((m.hw.regs[ADC+0x100] >> 16) & 31) == 16
    assert m.hw.regs[ADC+0x140] == 0 and m.hw.regs[ADC+0x108] == 1
    assert m.hw.regs[GPIO3+8] & 0x703 == 3, 'Encoder pins must remain inputs'
    assert m.hw.regs[GPIO3+0x18] & 0x700 == 0x700
    assert m.hw.regs[0x40038000] & 16
    rng = random.Random(68110)
    total = 0
    held = None
    m.u.mem_write(SCRATCH+4, bytes(4))
    for frame in range(5):
        expected = [0]*80
        for phase, spec in enumerate(model['scan']['phases']):
            work = int.from_bytes(m.u.mem_read(SYMS['native_scan_work'], 4), 'little')
            data = [rng.randrange(4096) for _ in range(18)]
            m.interrupt(data)
            for sample in spec['samples']:expected[sample['slot']] = data[sample['channel']]
            assert list(struct.unpack('<80H', m.u.mem_read(work, 160)))[phase*16:(phase+1)*16] == expected[phase*16:(phase+1)*16]
            ranks = [(m.hw.regs[ADC+0x120+i//4*4] >> (i%4*8)) & 31 for i in range(17)]
            assert ranks == model['scan']['initial_sequence'], ranks
            next_spec = model['scan']['phases'][(phase+1) % 5]
            p0, p3 = 0xf800, 3
            for port, bit in next_spec['select_low_pins']:
                if port == 0:p0 &= ~(1 << bit)
                else:p3 &= ~(1 << bit)
            assert m.hw.regs[0x40037000] & 0xf800 == p0
            assert m.hw.regs[GPIO3] & 3 == p3
            assert all(e[2] & 0xf800 == 0xf800 and e[3] & 3 == 3 for e in m.hw.events if e[0] == 'adc')
            assert not any(e[0] == 'write' and e[1] in (0x40039008, 0x40039014) for e in m.hw.events), 'Do not drive/discharge ADC pins'
            if held is not None:
                assert work != held
                assert bytes(m.u.mem_read(held, 160)) == held_data
            if phase < 4 and held is None:assert m.call('native_scan_acquire', SCRATCH, SCRATCH+4) == 0
            total += 1
        assert list(struct.unpack('<80H', m.u.mem_read(work, 160))) == expected
        if held is None:
            assert m.call('native_scan_acquire', SCRATCH, SCRATCH+4) == 1
            held = int.from_bytes(m.u.mem_read(SCRATCH, 4), 'little')
            held_data = bytes(m.u.mem_read(held, 160))
    m.call('native_scan_release')
    assert m.call('native_scan_acquire', SCRATCH, SCRATCH+4) == 1
    newest = int.from_bytes(m.u.mem_read(SCRATCH, 4), 'little')
    assert bytes(m.u.mem_read(newest, 160)) == struct.pack('<80H', *expected)
    m.call('native_scan_release')
    return total


def consumer(keyboard, start):
    return [int.from_bytes(p[1:3], 'little') for ep, p in keyboard.transfers[start:] if ep == 0x82 and len(p) == 3 and p[0] == 4]


def rotate(m, states):
    for state in states:
        old = int.from_bytes(m.u.mem_read(GPIO3+4, 4), 'little')
        m.u.mem_write(GPIO3+4, struct.pack('<I', (old & ~0x300) | (state << 8)))
        m.step()


def calibration_test():
    m = Keyboard()
    assert m.raw_command(bytes((0xa9,0x40,2)))[2] == 0
    for _ in range(10):m.step()
    # Different magnets may produce only 300..500 ADC counts over a full stroke.
    # None meets the old fixed 600-count threshold, but all have usable spans.
    mixed = [((1,0),300), ((1,14),400), ((2,14),500), ((3,13),350)]
    for rc, span in mixed:
        key = next(k for k in KEYS if k['matrix'] == list(rc))
        m.raw[key['raw_slot']] = key['hall']['released'] - span
    for _ in range(12):m.step()
    reply = m.raw_command(bytes((0xa9,0x41)))
    masks = [int.from_bytes(reply[4+r*3:7+r*3], 'little') for r in range(6)]
    for (row,col), span in mixed:
        assert masks[row] & (1 << col), ((row,col),span,reply.hex())
    assert not masks[2] & (1 << 2), 'Released W must not calibrate from idle noise'
    knob = m.raw_command(bytes((0xa9,0x42,4,13)))
    assert knob[5:9] == bytes(4) and not masks[4] & (1 << 13), 'The mechanical knob button has no Hall calibration'
    endpoints = {rc:struct.unpack_from('<2H',m.raw_command(bytes((0xa9,0x42,*rc))),5) for rc,span in mixed}
    for key in KEYS:m.raw[key['raw_slot']] = key['hall']['released']
    assert m.raw_command(bytes((0xa9,0x40,4)))[2] == 0
    m.step();m.save()
    restored = Keyboard(bytes(m.u.mem_read(LAYOUT.code_limit, LAYOUT.app_size-LAYOUT.code_limit)))
    for rc, pair in endpoints.items():
        assert struct.unpack_from('<2H',restored.raw_command(bytes((0xa9,0x42,*rc))),5) == pair, 'Small-span endpoints must survive reboot'


def profile_hotkey_test():
    for base in (0,2):
        m = Keyboard()
        m.call('default_layer_set', 1 << base)
        m.press('P');m.press('X')
        assert m.call('profile_get_current_index') == 0
        m.release('X');m.release('P')
        # Fn+Z remains a normal mute shortcut when P is not held.
        m.press('Fn');start = len(m.transfers)
        m.press('Z');m.release('Z')
        assert consumer(m,start) == [0xe2,0]
        assert m.call('profile_get_current_index') == 0
        start = len(m.transfers)
        m.press('P');assert not m.pressed(0x13)
        for name,index in (('X',1),('C',2),('Z',0)):
            m.press(name)
            assert m.call('profile_get_current_index') == index, (base,name,index)
            m.release(name)
        assert not consumer(m,start), 'Profile chords must not mute/play/stop'
        m.release('P');m.release('Fn')
        # Same-frame presses and releasing Fn before the other chord keys.
        start = len(m.transfers)
        for name in ('Fn','P','C'):m.travel_key(NAMES[name],140)
        m.step();assert m.call('profile_get_current_index') == 2
        m.release('Fn');m.release('C');m.release('P')
        assert not consumer(m,start)
        assert not any(m.reports()[-1][1:])
        m.save()
        restored = Keyboard(bytes(m.u.mem_read(LAYOUT.code_limit, LAYOUT.app_size-LAYOUT.code_limit)))
        assert restored.call('profile_get_current_index') == 2
        restored.press('A');assert restored.pressed(4)
        restored.release('A');assert not restored.pressed(4)


def main():
    cases = scanner_test()
    calibration_test()
    profile_hotkey_test()
    via, launcher = definitions(FIRMWARE, 'langtu/boom68/wired')
    assert next(k for k in launcher['layouts']['keys'] if (k['row'],k['col']) == (4,13))['ei'] == 0
    assert any('e0' in key for row in via['layouts']['keymap'] for key in row if isinstance(key,str))
    m = Keyboard()
    for key in KEYS:
        if key['name'] == 'Fn':continue
        usage = int(key['hid_usage'], 0)
        m.travel_key(key, 140);m.step();assert m.pressed(usage), key
        m.travel_key(key, 0);m.step();assert not m.pressed(usage), key
    # The digital button must work with a stopped ADC producer, bounce and VIA.
    m.call('dynamic_keymap_set_keycode', 0, 4, 13, 4)
    def button(down, elapsed):
        m.u.mem_write(GPIO3+4, struct.pack('<I', 0x300 if down else 0x700))
        m.tick += elapsed
        m.call('protocol_keyboard_task');m.drain()
    button(True, 1);assert not m.pressed(4)
    button(False, 1);button(True, 1);assert not m.pressed(4)
    button(True, 5);assert m.pressed(4)
    assert not m.call('sn34_he_idle') and not m.call('sn34_physical_released')
    for _ in range(4):m.step();assert m.pressed(4)
    button(False, 1);assert m.pressed(4)
    button(False, 5);assert not m.pressed(4)
    # One full detent per event; reversal/bounce and invalid jumps produce none.
    start = len(m.transfers)
    rotate(m, [2,3,2,0,1,3])
    assert consumer(m, start) == [0xe9, 0], consumer(m, start)
    start = len(m.transfers)
    rotate(m, [1,0,2,3])
    assert consumer(m, start) == [0xea, 0], consumer(m, start)
    start = len(m.transfers)
    rotate(m, [0,3]);assert not consumer(m, start)
    m.press('Fn')
    value = m.call('rgb_matrix_get_val')
    start = len(m.transfers)
    rotate(m, [2,0,1,3])
    assert m.call('rgb_matrix_get_val') > value and not consumer(m, start)
    m.release('Fn')
    # Both directions use the standard VIA encoder protocol and generate real
    # QMK key events after remapping, independently of the push button.
    for clockwise, code, states in ((1,4,[2,0,1,3]), (0,5,[1,0,2,3])):
        m.raw_command(bytes((0x15,0,0,clockwise,0,code)))
        assert m.raw_command(bytes((0x14,0,0,clockwise)))[4:6] == bytes((0,code))
        start = len(m.transfers)
        rotate(m,states)
        assert any(p[2+code//8] & (1 << (code%8)) for p in m.reports(start))
        assert not m.pressed(code)
    m.travel_key(NAMES['Fn'], 140);m.travel_key(NAMES['1 !'], 140);m.step();assert m.pressed(0x3a)
    m.release('1 !');m.release('Fn');assert not m.pressed(0x3a)
    # Verify every physical pixel reaches SPI in the OEM chain's GRB order.
    driver = struct.unpack('<4I', m.u.mem_read(SYMS['rgb_matrix_driver'], 16))
    m.call('HAL_SPI_TxCpltCallback', SYMS['rgb_spi'])
    m.call('rgb_matrix_set_color_all', 0, 0, 0)
    for index in (0,66,67,93):m.call('rgb_matrix_set_color', index, index+1, 7, 9)
    # call() expects symbol names; the driver's flush target may have a suffix.
    flush = next(name for name, value in SYMS.items() if value == driver[3] and name.startswith('flush'))
    m.call(flush)
    encoded = m.spi[-1]
    assert len(encoded) == 240+94*12
    lookup = [0x88,0x8e,0xe8,0xee]
    for index in range(94):
        colors = (7,index+1,9) if index in (0,66,67,93) else (0,0,0)
        want = bytes(lookup[(v>>shift)&3] for v in colors for shift in (6,4,2,0))
        assert encoded[120+index*12:132+index*12] == want, index
    assert not any(encoded[:120]+encoded[-120:])
    m.call('HAL_SPI_TxCpltCallback', SYMS['rgb_spi'])
    # Board-specific storage must preserve both Hall and digital remaps.
    m.remap('A', 5)
    assert m.save() != 0xffffffff
    restored = Keyboard(bytes(m.u.mem_read(LAYOUT.code_limit, LAYOUT.app_size-LAYOUT.code_limit)))
    restored.press('A');assert restored.pressed(5)
    restored.release('A')
    assert restored.call('dynamic_keymap_get_keycode', 0, 4, 13) == 4
    assert restored.call('dynamic_keymap_get_encoder', 0, 0, 1) == 4
    assert restored.call('dynamic_keymap_get_encoder', 0, 0, 0) == 5
    result = dict(status='PASS_OFFLINE_NOT_FLASHED', image_sha256=hashlib.sha256(IMAGE).hexdigest(),
                  hall_keys=67, digital_buttons=1, scan_phases=5, scanner_cases=cases, pixels=94,
                  tests=['OEM bank selection and 17 ADC ranks, including fixed SQR4',
                         'ADC inputs stay inputs; complete leased frames remain coherent',
                         'All 66 ordinary Hall keys and Fn traverse HE/QMK/USB',
                         'Debounced remappable knob button works without ADC frames',
                         'Quadrature direction, bounce cancellation and Fn brightness',
                         'All 94 RGB pixels, including both light-box endpoints, reach SPI',
                         'Hall and digital remaps survive a settings save/restart'])
    result['tests'] += ['Mixed 300..500-count Hall spans calibrate individually; idle keys and the knob button do not',
                        'Both encoder directions are exposed in Launcher/VIA, remappable by protocol and persistent']
    result['tests'] += ['Fn+P+Z/X/C switches all profiles on Windows/macOS, including simultaneous presses and reordered releases, without media events; selection persists']
    (BUILD/'boom68_results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':main()
