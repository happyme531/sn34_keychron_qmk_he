# /// script
# dependencies = ["pyelftools"]
# ///
"""Export VIA and Launcher definitions from keyboard.json and a compiled QMK ELF."""
import argparse
import json
import os
from pathlib import Path
from firmware import Firmware, keyboard_definition, keyboard_file


def definitions(firmware, keyboard=None):
    keyboard = keyboard or os.environ.get('SN34_KEYBOARD', 'battle68')
    firmware.validate_keyboard(keyboard)
    board = keyboard_definition(keyboard)
    configurator = json.loads(keyboard_file('board/configurator.json', keyboard).read_text(encoding='utf-8'))
    encoders = {tuple(item['matrix']):item['index'] for item in configurator.get('encoders', [])}
    if encoders and 'encoder_map' not in firmware.symbols:
        raise ValueError('Configured encoders require a compiled encoder map')
    layout = sorted(board['layouts']['LAYOUT']['layout'], key=lambda key: (key['y'], key['x']))
    rows = []
    for y in sorted({key['y'] for key in layout}):
        row, cursor = [], 0
        for key in (key for key in layout if key['y'] == y):
            config = {}
            if abs(key['x'] - cursor) > 0.02:
                config['x'] = round(key['x'] - cursor, 3)
            if abs(key.get('w', 1) - 1) > 0.02:
                config['w'] = key['w']
            if config:
                row.append(config)
            legend = ','.join(map(str, key['matrix']))
            if tuple(key['matrix']) in encoders:
                legend += '\n\n\n\n\n\n\n\n\ne' + str(encoders[tuple(key['matrix'])])
            row.append(legend)
            cursor = key['x'] + key.get('w', 1)
        rows.append(row)
    menus = []
    if firmware.features['rgb']:
        controls = [
            dict(label='Brightness', type='range', options=[0,255], content=['id_qmk_rgb_matrix_brightness',3,1]),
            dict(label='Effect', type='dropdown', options=[[p['label'],p['wire']] for p in firmware.rgb_protocol], content=['id_qmk_rgb_matrix_effect',3,2]),
            dict(label='Effect Speed', type='range', options=[0,255], content=['id_qmk_rgb_matrix_effect_speed',3,3]),
            dict(label='Color', type='color', content=['id_qmk_rgb_matrix_color',3,4]),
        ]
        menus = [dict(label='Lighting', content=[dict(label='Backlight', content=controls)])]
    pins = board['matrix_pins']
    via = dict(name=board['keyboard_name'], vendorId=board['usb']['vid'], productId=board['usb']['pid'],
               matrix=dict(rows=len(pins['rows']), cols=len(pins['cols'])), layouts=dict(keymap=rows),
               menus=menus, keycodes=['qmk_lighting'] if menus else [], firmwareVersion=5)
    keys = [dict(row=key['matrix'][0], col=key['matrix'][1], x=key['x'], y=key['y'],
                 r=0, rx=0, ry=0, d=False, w=key.get('w',1), h=key.get('h',1), color='alpha') for key in layout]
    for key in keys:
        if (key['row'], key['col']) in encoders:
            key['ei'] = encoders[key['row'], key['col']]
    labels = configurator['layers']
    if len(labels) != board['dynamic_keymap']['layer_count']:
        raise ValueError('Configurator labels must match the QMK layer count')
    launcher = dict(name=via['name'], vendorId=via['vendorId'], productId=via['productId'],
                    vendorProductId=(int(via['vendorId'],0)<<16)|int(via['productId'],0), firmwareVersion=5,
                    feature=['HE'], accuration=0.1, menus=menus, keycodes=via['keycodes'], customKeycodes=[],
                    matrix=via['matrix'], layers=labels,
                    layouts=dict(width=max(k['x']+k['w'] for k in keys), height=max(k['y']+k['h'] for k in keys),
                                 optionKeys={}, keys=keys))
    return via, launcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('--keyboard', default='battle68')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    firmware = Firmware(args.elf)
    output = args.output_dir or args.elf.parent / (args.elf.stem + '_config')
    via, launcher = definitions(firmware, args.keyboard)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('sn34_via.json',via), ('sn34_launcher.json',launcher)]:
        path = output/name
        path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        print(path)


if __name__ == '__main__':
    main()
