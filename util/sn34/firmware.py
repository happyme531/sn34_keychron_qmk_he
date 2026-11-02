"""Read a standard QMK ELF for optional SN34 packaging and configurator exports."""
from io import BytesIO
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def keyboard_definition(keyboard=None):
    keyboard = keyboard or os.environ.get('SN34_KEYBOARD', 'battle68')
    if not re.fullmatch(r'[a-z0-9_]+(?:/[a-z0-9_]+)*', keyboard):
        raise ValueError(f'Invalid keyboard name: {keyboard}')
    return json.loads((ROOT / 'keyboards' / keyboard / 'keyboard.json').read_text(encoding='utf-8'))


class Firmware:
    def __init__(self, path):
        from elftools.elf.elffile import ELFFile
        self.path = Path(path).resolve()
        self.elf = ELFFile(BytesIO(self.path.read_bytes()))
        self.symbols = {s.name: s for s in self.elf.get_section_by_name('.symtab').iter_symbols()}
        self.addresses = {name: s.entry.st_value for name, s in self.symbols.items()}
        self.memory = {name[len('__sn34_'):].lower(): value for name, value in self.addresses.items()
                       if name.startswith('__sn34_')}
        self.base = self.memory['app_origin']
        segments = [s for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_filesz']]
        end = max(s['p_paddr'] + s['p_filesz'] for s in segments)
        if any(s['p_paddr'] < self.base for s in segments) or end >= self.memory['code_limit']:
            raise ValueError('ELF load segments overlap reserved memory')
        image = bytearray(end - self.base)
        for segment in segments:
            start = segment['p_paddr'] - self.base
            image[start:start + segment['p_filesz']] = segment.data()
        self.code = bytes(image)
        if (int.from_bytes(self.code[:4], 'little') != self.memory['stack_top']
                or self.addresses['__bss_end'] > self.memory['bss_limit']):
            raise ValueError('ELF does not satisfy the target RAM/stack contract')

    def read_symbol(self, name):
        symbol = self.symbols[name]
        section = self.elf.get_section(symbol['st_shndx'])
        offset = symbol['st_value'] - section['sh_addr']
        return section.data()[offset:offset + symbol['st_size']]

    def validate_keyboard(self, keyboard):
        board = keyboard_definition(keyboard)
        descriptor = self.read_symbol('device_desc')
        identity = tuple(int.from_bytes(descriptor[offset:offset + 2], 'little') for offset in (8, 10))
        if identity != (int(board['usb']['vid'], 0), int(board['usb']['pid'], 0)):
            raise ValueError('ELF USB identity does not match the selected keyboard')

    @property
    def features(self):
        return dict(rgb='rgb_matrix_task' in self.symbols, xinput='sn34_xinput_class' in self.symbols,
                    ota='ota_report' in self.symbols)

    @property
    def rgb_protocol(self):
        result = [dict(wire=0, core=0, name='NONE', label='None')]
        if not self.features['rgb']:
            return result
        names = {int(wire): name for name, wire in re.findall(r'SN34_RGB_EFFECT\((\w+), (\d+)\)',
                 (ROOT / 'tmk_core/protocol/sn34/rgb_protocol.inc').read_text(encoding='utf-8'))}
        for wire, core in enumerate(self.read_symbol('sn34_rgb_wire_to_core')):
            if not wire or core == 255:
                continue
            name = names[wire]
            label = name.replace('_', ' ').title()
            if wire <= 22 and name.startswith('SOLID_REACTIVE_'):
                label = label.removeprefix('Solid ')
            result.append(dict(wire=wire, core=core, name=name, label=label))
        return result

    def application(self):
        result = bytearray(self.memory['app_size'])
        result[:len(self.code)] = self.code
        address = self.memory['footer_address'] - self.base
        result[address:address + 4] = self.memory['footer_magic'].to_bytes(4, 'little')
        return bytes(result)
