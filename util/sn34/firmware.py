"""Read a standard QMK ELF for optional SN34 packaging and configurator exports."""
from io import BytesIO
import json
import os
from pathlib import Path
import re
from settings import BATTLE68_EEPROM_MAGIC

ROOT = Path(__file__).resolve().parents[2]


def keyboard_directory(keyboard=None):
    keyboard = keyboard or os.environ.get('SN34_KEYBOARD', 'battle68')
    if not re.fullmatch(r'[a-z0-9_]+(?:/[a-z0-9_]+)*', keyboard):
        raise ValueError(f'Invalid keyboard name: {keyboard}')
    return ROOT / 'keyboards' / keyboard


def keyboard_file(relative, keyboard=None):
    """Find the nearest board resource through QMK's keyboard hierarchy."""
    directory = keyboard_directory(keyboard)
    while directory != ROOT / 'keyboards':
        path = directory / relative
        if path.is_file():
            return path
        directory = directory.parent
    raise FileNotFoundError(f'No inherited {relative} for {keyboard or directory}')


def keyboard_definition(keyboard=None):
    """Read maintained JSON metadata without requiring a QMK CLI on USB hosts.

    Follow this checkout's find_info_json/deep_update order and per-key layout
    merge. Config.h/rules.mk interpretation remains QMK's responsibility.
    """
    def merge(destination, source):
        for key, value in source.items():
            if isinstance(value, dict):
                merge(destination.setdefault(key, {}), value)
            else:
                destination[key] = value

    result = {'layouts': {}}
    directory = keyboard_directory(keyboard)
    while directory != ROOT / 'keyboards':
        for name in ('info.json', 'keyboard.json'):
            path = directory / name
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            if 'layout_aliases' in data:
                result.setdefault('layout_aliases', {}).update(data.pop('layout_aliases'))
            for name, layout in data.pop('layouts', {}).items():
                name = result.get('layout_aliases', {}).get(name, name)
                if name not in result['layouts']:
                    result['layouts'][name] = layout
                else:
                    existing = result['layouts'][name]['layout']
                    if len(existing) != len(layout['layout']):
                        raise ValueError(f'Inherited {name} has a different number of keys')
                    for old, new in zip(existing, layout['layout']):
                        old.update(new)
            merge(result, data)
        directory = directory.parent
    if not result.get('usb'):
        raise ValueError('Keyboard metadata has no USB identity')
    return result


def keyboard_layout(board, name=None):
    """Select a maintained layout; require a choice when several are available."""
    layouts = board.get('layouts', {})
    name = name or os.environ.get('SN34_LAYOUT')
    if name:
        name = board.get('layout_aliases', {}).get(name, name)
    elif len(layouts) == 1:
        name = next(iter(layouts))
    if name not in layouts:
        raise ValueError('Select --layout from: ' + ', '.join(sorted(layouts)))
    return layouts[name]['layout']


class Firmware:
    def __init__(self, path):
        from elftools.elf.elffile import ELFFile
        self.path = Path(path).resolve()
        self.elf = ELFFile(BytesIO(self.path.read_bytes()))
        self.symbols = {s.name: s for s in self.elf.get_section_by_name('.symtab').iter_symbols()}
        self.addresses = {name: s.entry.st_value for name, s in self.symbols.items()}
        self.memory = {name[len('__sn34_'):].lower(): value for name, value in self.addresses.items()
                       if name.startswith('__sn34_')}
        # Pre-policy Battle68 ELFs accepted v1/v2. Do not infer that ABI for
        # another keyboard whose ELF predates the explicit legacy bitmap.
        self.memory.setdefault('eeprom_legacy_versions',
                               (1 << 1) | (1 << 2) if self.memory['eeprom_magic'] == BATTLE68_EEPROM_MAGIC else 0)
        self.base = self.memory['app_origin']
        if self.base != 0:
            raise ValueError('SN34F280 application must start at User-ROM offset zero')
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
                 (ROOT / 'drivers/analog/keychron_he/rgb_protocol.inc').read_text(encoding='utf-8'))}
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
