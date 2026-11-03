"""Link the production memory script with valid and invalid board configurations.

Run in the ARM build environment: uv run tests/sn34/test_compile_contracts.py
"""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMPILER = shutil.which('arm-none-eabi-gcc')


@unittest.skipUnless(COMPILER, 'ARM GNU toolchain required for linker contract tests')
class LinkerContracts(unittest.TestCase):
    def setUp(self):
        (ROOT / '.build').mkdir(exist_ok=True)
        temporary = TemporaryDirectory(dir=ROOT / '.build')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / 'probe.c'
        self.source.write_text('__attribute__((section(".vectors"), used))\n'
                               'const unsigned vectors[] = {0x20028000, 1};\n'
                               'void sn34_reset_entry(void) {}\n')

    def link(self, **overrides):
        config = dict(SN34_EEPROM_BANK_SIZE='0x2000', SN34_EEPROM_BASE='0x25',
                      SN34_EEPROM_MAGIC='0x1234', SN34_EEPROM_COMMIT='0x5678',
                      SN34_EEPROM_VERSION='1', SN34_EEPROM_BANK0='0x79000', SN34_EEPROM_BANK1='0x7b000')
        config.update(overrides)
        (self.directory / 'board_config.h').write_text(
            ''.join(f'#define {key} {value}\n' for key, value in config.items()) + '#include "sn34_defaults.h"\n')
        script = self.directory / 'probe.ld'
        preprocess = subprocess.run([COMPILER, '-E', '-P', '-x', 'c', '-I' + str(self.directory),
                                     '-Iplatforms/sn34/include', 'platforms/sn34/sn34f28x/application.ld.S',
                                     '-o', str(script)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(preprocess.returncode, 0, preprocess.stderr)
        return subprocess.run([COMPILER, '-mcpu=cortex-m4', '-mthumb', '-nostdlib',
                               '-Wl,-T,' + str(script), str(self.source), '-o', str(self.directory / 'probe.elf')],
                              cwd=ROOT, capture_output=True, text=True)

    def test_valid_banks_in_either_order_link(self):
        for config in ({}, {'SN34_EEPROM_BANK0': '0x7b000', 'SN34_EEPROM_BANK1': '0x79000'}):
            with self.subTest(config=config):
                result = self.link(**config)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_memory_contracts_fail_linking(self):
        cases = [
            ({'SN34_EEPROM_BANK1': '0x79000'}, 'EEPROM banks overlap'),
            ({'SN34_EEPROM_BANK1': '0x79200'}, 'EEPROM banks overlap'),
            ({'SN34_EEPROM_BANK0': '0x79001'}, 'page aligned'),
            ({'SN34_EEPROM_BANK1': '0x7de00'}, 'overlaps application footer'),
            ({'SN34_EEPROM_BANK_SIZE': '0x2001'}, 'whole payload pages'),
            ({'SN34_EEPROM_SIZE': '512'}, 'whole payload pages'),
            ({'SN34_CODE_LIMIT': '0x7b000'}, 'code limit must precede'),
            ({'SN34_EEPROM_END': '0x7c000'}, 'end must cover both banks'),
            ({'SN34_FOOTER_PAGE': '0x7d000'}, 'final application page'),
            ({'SN34_FOOTER_ADDRESS': '0x7dff8'}, 'final application page'),
            ({'SN34_BSS_LIMIT': '0x20028000'}, 'heap and stack must fit RAM'),
        ]
        for config, reason in cases:
            with self.subTest(config=config):
                result = self.link(**config)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reason, result.stderr)


if __name__ == '__main__':
    unittest.main()
