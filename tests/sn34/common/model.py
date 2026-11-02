"""Join independent measured fixtures to QMK display metadata for offline tests."""
import hashlib
import json
from target import ROOT, board_directory, keyboard_name

def keyboard_definition(path=None):
    path=path or ROOT/'keyboards'/keyboard_name()/'keyboard.json'
    return json.loads(path.read_text(encoding='utf-8'))

def matrix_digest(keys):
    coordinates=sorted([[key['raw_slot'],*key['matrix']] for key in keys])
    return hashlib.sha256(json.dumps(coordinates,separators=(',',':')).encode()).hexdigest()

def load_board(path=None,metadata=None):
    board=json.loads((path or board_directory()/'board.json').read_text(encoding='utf-8'))
    metadata=metadata or keyboard_definition()
    board['matrix'].update(rows=len(metadata['matrix_pins']['rows']),cols=len(metadata['matrix_pins']['cols']))
    layout={tuple(key['matrix']):key for key in metadata['layouts']['LAYOUT']['layout']}
    leds=metadata.get('rgb_matrix',{}).get('layout',[])
    indices={tuple(led['matrix']):i for i,led in enumerate(leds) if 'matrix' in led}
    for key in board['keys']:
        key['layout']=layout[tuple(key['matrix'])]
        key['name']=key['layout']['label']
        key['led']=indices.get(tuple(key['matrix']))
    board.update(name=metadata['keyboard_name'],usb=metadata['usb'],leds={'count':len(leds),'layout':leds})
    return board
