# /// script
# dependencies = ["unicorn", "pyelftools", "capstone", "hidapi", "pefile"]
# ///
"""Run host and firmware regressions directly against a standard QMK ELF."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
from target import ROOT, target_tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keyboard', default='battle68')
    parser.add_argument('--keymap', default='default')
    parser.add_argument('--elf', type=Path)
    parser.add_argument('--unit-only', action='store_true')
    args = parser.parse_args()
    elf = (args.elf or ROOT/'.build'/(args.keyboard.replace('/','_')+'_'+args.keymap+'.elf')).resolve()
    logs = ROOT/'.build/sn34-tests'/elf.stem
    logs.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'SN34_KEYBOARD':args.keyboard, 'SN34_KEYMAP':args.keymap,
           'SN34_ELF':str(elf), 'SN34_NATIVE_BUILD':str(logs)}
    # Compatibility fixtures describe Battle68; firmware-product tests use the selected ELF.
    units = ['test_build.py', 'test_host.py', 'test_he_protocol.py', 'test_backup.py', 'test_platform.py']
    if args.keyboard == 'battle68':
        units.append('test_sn34_contracts.py')
    for name in units:
        subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests/sn34'),'-p',name],
                       cwd=ROOT, env=env, check=True)
    if args.unit_only:
        return
    results = []
    for test in target_tests(args.keyboard,args.keymap):
        path = logs/(Path(test).stem+'.log')
        with path.open('w',encoding='utf-8') as stream:
            result = subprocess.run([sys.executable,str(ROOT/'tests/sn34'/test)],
                                    cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit(path.read_text(encoding='utf-8'))
        results.append(test)
        print('PASS '+test,flush=True)
    print(json.dumps(dict(elf=str(elf),passed=results),indent=2))


if __name__ == '__main__':
    main()
