# /// script
# dependencies = ["hidapi", "pyelftools"]
# ///
"""Back up settings, prepare an application image and flash it with SonixFlasherC."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from backup import capture
from device import Raw
from firmware import Firmware, keyboard_definition
from package import preserve_settings
from settings import read_banks, newest_bank


def migrated_payload(record, memory):
    payload = record['payload']
    if record['version'] == 2 and memory['eeprom_version'] >= 3:
        if any(payload[-2:]):
            raise ValueError('v2 macros need shortening before migration')
        start = memory['eeprom_base'] + 1
        payload = payload[:start + 1] + payload[start:-1]
    return payload


def verify_settings(firmware, expected, timeout=15):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        raw = None
        try:
            raw = Raw()
            image, _ = capture(raw, firmware)
            actual = newest_bank(read_banks(image, firmware.memory))['payload']
            if expected is not None and actual != expected:
                raise ValueError('Settings after reboot differ from the backup; keep the saved backup for recovery')
            return raw.query((0xa1,))[1:].split(b'\0', 1)[0].decode('ascii')
        except (OSError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.5)
        finally:
            if raw is not None:
                raw.close()
    raise RuntimeError(f'Firmware did not reconnect for verification: {last_error}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('--keyboard', default='battle68')
    parser.add_argument('--flasher', default=os.environ.get('SN34_FLASHER', 'sonixflasher'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--prepare-only', action='store_true', help='Create reviewable files without requesting a reboot')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--settings-backup', type=Path, help='Existing application readback or settings snapshot')
    selection.add_argument('--reset-settings', action='store_true', help='Explicitly initialize default settings after flash')
    args = parser.parse_args()
    os.environ['SN34_KEYBOARD'] = args.keyboard
    firmware = Firmware(args.elf)
    firmware.validate_keyboard(args.keyboard)
    flasher = shutil.which(args.flasher)
    if not args.prepare_only and not flasher:
        parser.error('SonixFlasherC executable not found; set --flasher or SN34_FLASHER')
    application = firmware.application()
    backup = metadata = expected = None
    if args.settings_backup:
        backup = args.settings_backup.read_bytes()
        metadata = dict(kind='existing-backup', path=str(args.settings_backup.resolve()))
    elif not args.reset_settings:
        raw = Raw()
        try:
            backup, metadata = capture(raw, firmware)
        finally:
            raw.close()
    if backup is not None:
        application, preserved = preserve_settings(application, backup, firmware)
        expected = migrated_payload(newest_bank(read_banks(backup, firmware.memory)), firmware.memory)
        metadata.update(preserved)
    # Validate the complete image before a flasher can send an OTA request.
    memory = firmware.memory
    if len(application) != memory['app_size'] or int.from_bytes(application[-4:], 'little') != memory['footer_magic']:
        raise ValueError('Application length/footer does not match the target')
    output = args.output_dir or firmware.path.parent / (firmware.path.stem + '_flash') / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True, exist_ok=False)
    if backup is not None:
        (output / 'settings-backup.bin').write_bytes(backup)
    image = output / 'application.bin'
    image.write_bytes(application)
    board = keyboard_definition(args.keyboard)
    usb = board['usb']
    command = [flasher or args.flasher, '-v', f"{int(usb['vid'], 0):04x}/{int(usb['pid'], 0):04x}",
               '--boot-vid-pid', '0c45/7210', '-r', 'sonix', '-o', '0', '-f', str(image.resolve())]
    record = dict(keyboard=args.keyboard, application_sha256=hashlib.sha256(application).hexdigest(),
                  settings=metadata, reset_settings=args.reset_settings, command=command, status='prepared')
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)
    if args.prepare_only:
        return
    # All files, settings checks and the recovery backup exist before this call.
    try:
        subprocess.run(command, check=True)
        record['firmware_reported'] = verify_settings(firmware, expected)
        record.update(status='verified', settings_verified=expected is not None)
    except Exception:
        record['status'] = 'failed-or-unverified'
        raise
    finally:
        manifest.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
