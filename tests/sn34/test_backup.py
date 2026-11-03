"""Execute settings snapshots and non-destructive flash preparation."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent / 'common'),
               str(Path(__file__).resolve().parents[2] / 'util/sn34')]
from keyboard import Keyboard, KEYS
from emulator import FIRMWARE, SYMS
from target import ROOT, keyboard_name
from backup import capture, request
from settings import read_banks, snapshot_image
from package import preserve_settings
import flash


class EmulatedRaw:
    info = {'serial_number': 'EMULATED'}

    def __init__(self, keyboard):
        self.keyboard = keyboard
        self.change_once = False
        self.closed = False

    def close(self):
        self.closed = True

    def query(self, packet):
        if packet[0:2] == bytes((0xb0, 1)) and self.change_once:
            self.change_once = False
            self.keyboard.call('eeprom_update_byte', FIRMWARE.memory['eeprom_size'] - 1, 1)
        return self.keyboard.raw_command(bytes(packet))


class SettingsSnapshots(unittest.TestCase):
    def test_unactuated_hall_noise_does_not_block_read_only_snapshot(self):
        keyboard = Keyboard()
        keyboard.travel_key(KEYS[0], 12)
        keyboard.step()
        self.assertFalse(keyboard.call('sn34_physical_released'))
        self.assertTrue(keyboard.call('sn34_he_idle'))
        image, _ = capture(EmulatedRaw(keyboard), FIRMWARE)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'],
                         bytes(keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size'])))

    def test_live_cache_round_trip_includes_unsaved_settings(self):
        keyboard = Keyboard()
        keyboard.call('dynamic_keymap_set_keycode', 0, *KEYS[0]['matrix'], 5)
        keyboard.raw_command(bytes((0xa9, 0x11, 1)))
        before = bytes(keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size']))
        writes = list(keyboard.flash)
        image, metadata = capture(EmulatedRaw(keyboard), FIRMWARE)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'], before)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['version'], FIRMWARE.memory['eeprom_version'])
        self.assertFalse(metadata['code_backup'])
        self.assertFalse(any(image[:FIRMWARE.memory['code_limit']]))
        self.assertEqual(keyboard.flash, writes)
        application, _ = preserve_settings(FIRMWARE.application(), image, FIRMWARE)
        restored = Keyboard(application[FIRMWARE.memory['code_limit']:])
        self.assertEqual(bytes(restored.u.mem_read(SYMS['cache'], len(before))), before)

    def test_changed_revision_restarts_the_snapshot(self):
        keyboard = Keyboard()
        raw = EmulatedRaw(keyboard)
        raw.change_once = True
        image, _ = capture(raw, FIRMWARE)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'],
                         bytes(keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size'])))
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'][-1], 1)

    def test_bounds_rejected_but_input_and_calibration_do_not_block_reads(self):
        keyboard = Keyboard()
        raw = EmulatedRaw(keyboard)
        revision = struct.unpack_from('<I', request(raw, 0), 4)[0]
        for offset, count in ((65535, 22), (0, 23), (0, 0), (FIRMWARE.memory['eeprom_size'], 1)):
            with self.assertRaises(ValueError):
                request(raw, 1, revision, offset, count)
        keyboard.travel_key(KEYS[0], 140)
        keyboard.step()
        self.assertFalse(keyboard.call('sn34_he_idle'))
        image, _ = capture(raw, FIRMWARE)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'],
                         bytes(keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size'])))
        calibrating = EmulatedRaw(Keyboard())
        calibrating.query(bytes((0xa9, 0x40, 2)))
        image, _ = capture(calibrating, FIRMWARE)
        self.assertEqual(read_banks(image, FIRMWARE.memory)[0]['payload'],
                         bytes(calibrating.keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size'])))

    def test_v2_full_macro_tail_is_rejected_before_packaging(self):
        memory = dict(FIRMWARE.memory, eeprom_version=2)
        payload = bytearray(memory['eeprom_size'])
        payload[-2] = 1
        reason = 'macro buffer' if memory['eeprom_legacy_versions'] & (1 << 2) else 'compatible committed settings bank'
        with self.assertRaisesRegex(ValueError, reason):
            preserve_settings(FIRMWARE.application(), snapshot_image(payload, memory), FIRMWARE)

    def test_post_flash_verification_detects_a_changed_setting(self):
        raw = EmulatedRaw(Keyboard())
        expected = bytearray(raw.keyboard.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size']))
        expected[-1] ^= 1
        with patch.object(flash, 'Raw', return_value=raw), self.assertRaisesRegex(ValueError, 'differ from the backup'):
            flash.verify_settings(FIRMWARE, expected)
        self.assertTrue(raw.closed)


class Preparation(unittest.TestCase):
    def test_prepare_only_does_not_open_or_reboot_a_device(self):
        with TemporaryDirectory(dir=ROOT / '.build') as temporary:
            output = Path(temporary) / 'prepared'
            args = ['flash.py', str(FIRMWARE.path), '--keyboard', keyboard_name(),
                    '--reset-settings', '--prepare-only', '--output-dir', str(output)]
            with patch.object(sys, 'argv', args), patch.object(flash, 'Raw') as raw, \
                    patch.object(flash.subprocess, 'run') as execute, contextlib.redirect_stdout(io.StringIO()):
                flash.main()
            raw.assert_not_called()
            execute.assert_not_called()
            record = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(record['status'], 'prepared')
            self.assertEqual((output / 'application.bin').read_bytes(), FIRMWARE.application())
            self.assertNotIn('-j', record['command'])
            self.assertEqual(record['command'][record['command'].index('-o') + 1], '0')

    def test_missing_flasher_aborts_before_backup(self):
        args = ['flash.py', str(FIRMWARE.path), '--keyboard', keyboard_name(), '--flasher', 'not-an-installed-flasher']
        with patch.object(sys, 'argv', args), patch.object(flash, 'Raw') as raw, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            flash.main()
        raw.assert_not_called()

    def test_unsupported_snapshot_aborts_before_invoking_the_flasher(self):
        args = ['flash.py', str(FIRMWARE.path), '--keyboard', keyboard_name()]
        with patch.object(sys, 'argv', args), patch.object(flash.shutil, 'which', return_value='flasher'), \
                patch.object(flash, 'Raw') as raw, patch.object(flash.subprocess, 'run') as execute:
            raw.return_value.query.side_effect = RuntimeError('Firmware rejected command')
            with self.assertRaisesRegex(RuntimeError, '--settings-backup'):
                flash.main()
        raw.return_value.close.assert_called_once()
        execute.assert_not_called()

    def test_auto_backup_precedes_flash_and_full_cache_is_verified(self):
        original = Keyboard()
        original.call('dynamic_keymap_set_keycode', 0, *KEYS[0]['matrix'], 5)
        expected = bytes(original.u.mem_read(SYMS['cache'], FIRMWARE.memory['eeprom_size']))
        raws = [EmulatedRaw(original)]
        with TemporaryDirectory(dir=ROOT / '.build') as temporary:
            output = Path(temporary) / 'transaction'

            def execute(command, check):
                self.assertTrue(check)
                image = Path(command[command.index('-f') + 1]).read_bytes()
                backup = (output / 'settings-backup.bin').read_bytes()
                self.assertEqual(read_banks(backup, FIRMWARE.memory)[0]['payload'], expected)
                self.assertTrue(raws[0].closed)
                self.assertEqual(json.loads((output / 'manifest.json').read_text())['status'], 'prepared')
                raws.append(EmulatedRaw(Keyboard(image[FIRMWARE.memory['code_limit']:])))

            args = ['flash.py', str(FIRMWARE.path), '--keyboard', keyboard_name(), '--output-dir', str(output)]
            with patch.object(sys, 'argv', args), patch.object(flash.shutil, 'which', return_value='flasher'), \
                    patch.object(flash, 'Raw', side_effect=lambda: raws[-1]), \
                    patch.object(flash.subprocess, 'run', side_effect=execute) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                flash.main()
            run.assert_called_once()
            record = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(record['status'], 'verified')
            self.assertTrue(record['settings_verified'])
            self.assertTrue(all(raw.closed for raw in raws))

    def test_failed_flasher_keeps_backup_and_marks_manifest(self):
        with TemporaryDirectory(dir=ROOT / '.build') as temporary:
            output = Path(temporary) / 'failed'
            raw = EmulatedRaw(Keyboard())
            args = ['flash.py', str(FIRMWARE.path), '--keyboard', keyboard_name(), '--output-dir', str(output)]
            with patch.object(sys, 'argv', args), patch.object(flash.shutil, 'which', return_value='flasher'), \
                    patch.object(flash, 'Raw', return_value=raw), \
                    patch.object(flash.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'flasher')), \
                    patch.object(flash, 'verify_settings') as verify, contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaises(subprocess.CalledProcessError):
                flash.main()
            self.assertTrue((output / 'settings-backup.bin').is_file())
            self.assertEqual(json.loads((output / 'manifest.json').read_text())['status'], 'failed-or-unverified')
            self.assertTrue(raw.closed)
            verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
