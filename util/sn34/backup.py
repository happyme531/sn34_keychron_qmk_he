# /// script
# dependencies = ["hidapi", "pyelftools"]
# ///
"""Save a consistent, read-only SN34 settings snapshot (not a code rollback image)."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import struct

from device import Raw
from firmware import Firmware, keyboard_definition
from settings import snapshot_image

COMMAND = 0xb0


def request(raw, op, revision=0, offset=0, count=0):
    packet = bytearray(32)
    packet[:2] = bytes((COMMAND, op))
    struct.pack_into('<IH', packet, 4, revision, offset)
    packet[10] = count
    reply = raw.query(packet)
    if len(reply) != 32 or reply[:2] != packet[:2] or reply[3] != 1:
        raise ValueError('Unsupported settings snapshot response')
    if reply[2] not in (0, 3):
        raise ValueError('Settings snapshot request rejected')
    return reply


def capture(raw, firmware):
    """Read the live cache with a revision check on every packet."""
    memory = firmware.memory
    board = keyboard_definition()
    for _ in range(3):
        try:
            info = request(raw, 0)
        except (RuntimeError, ValueError, OSError) as exc:
            raise RuntimeError('Settings backup unavailable. Older firmware needs an existing '
                               '--settings-backup for the first upgrade; no reboot was requested. ' + str(exc)) from exc
        size, base = struct.unpack_from('<HH', info, 8)
        identity = struct.unpack_from('<4I', info, 14)
        if (info[2] or info[12] != memory['eeprom_version'] or size != memory['eeprom_size'] or
                base != memory['eeprom_base'] or identity != tuple(memory[key] for key in
                    ('eeprom_bank0', 'eeprom_bank1', 'eeprom_magic', 'eeprom_commit')) or
                tuple(info[30:32]) != (len(board['matrix_pins']['rows']), len(board['matrix_pins']['cols']))):
            raise ValueError('Device settings layout does not match the selected firmware')
        revision = struct.unpack_from('<I', info, 4)[0]
        payload = bytearray()
        for offset in range(0, size, 22):
            count = min(22, size - offset)
            reply = request(raw, 1, revision, offset, count)
            if reply[2] == 3:
                break
            if struct.unpack_from('<IH', reply, 4) != (revision, offset):
                raise ValueError('Settings snapshot revision/offset mismatch')
            payload.extend(reply[10:10 + count])
        if len(payload) == size:
            return snapshot_image(payload, memory), dict(kind='sn34-settings-snapshot',
                keyboard=os.environ.get('SN34_KEYBOARD', 'battle68'), serial=raw.info.get('serial_number'),
                revision=revision, storage_version=info[12], payload_sha256=hashlib.sha256(payload).hexdigest(),
                code_backup=False)
    raise RuntimeError('Settings changed during all three snapshot attempts; no backup was written')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('--keyboard', default='battle68')
    parser.add_argument('--serial')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    os.environ['SN34_KEYBOARD'] = args.keyboard
    if args.serial:
        os.environ['SN34_DEVICE_SERIAL'] = args.serial
    firmware = Firmware(args.elf)
    firmware.validate_keyboard(args.keyboard)
    raw = Raw()
    try:
        image, metadata = capture(raw, firmware)
    finally:
        raw.close()
    output = args.output or firmware.path.parent / (firmware.path.stem + '_settings_' +
                          datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.bin')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(image)
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
