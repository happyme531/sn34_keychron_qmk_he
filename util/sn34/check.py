"""Run target-specific firmware checks and shared host/model regressions."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from build_config import ROOT

UNITS=('test_sn34_contracts.py','test_build.py','test_model.py','test_host.py')
FIRMWARE=('test_bat68.py','test_sn34_features.py','test_sn34_usb.py','test_storage.py',
          'test_sn34_lifecycle.py','test_native_scan.py','test_native_boot.py','test_keychron_eeprom.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keyboard',default='battle68')
    parser.add_argument('--keymap',default='default')
    parser.add_argument('--build-dir',type=Path)
    parser.add_argument('--unit-only',action='store_true')
    args=parser.parse_args()
    for pattern in UNITS:
        env={**os.environ,'SN34_KEYBOARD':'battle68'}
        subprocess.run([sys.executable,'-m','unittest','discover','-s','tests/sn34','-p',pattern],cwd=ROOT,env=env,check=True)
    if args.unit_only:return
    build=(ROOT/args.build_dir).resolve() if args.build_dir else ROOT/'.build/sn34'/args.keyboard/args.keymap
    manifest=json.loads((build/'manifest.json').read_text(encoding='utf-8'))
    if (manifest['keyboard'],manifest['keymap'])!=(args.keyboard,args.keymap):
        raise ValueError('Selected firmware does not match the requested keyboard/keymap')
    env={**os.environ,'SN34_KEYBOARD':args.keyboard,'SN34_NATIVE_BUILD':str(build)}
    tests=('test_second_target.py',) if args.keyboard=='sn34_test' else ('test_sn34_hooks.py',) if args.keymap=='minimal' else FIRMWARE
    logs=build/'test_logs';logs.mkdir(exist_ok=True)
    for name in tests:
        path=logs/(Path(name).stem+'.log')
        with path.open('w',encoding='utf-8') as stream:
            command=[sys.executable,str(ROOT/'tests/sn34'/name)]
            if name=='test_second_target.py':command+=['--build-dir',str(build)]
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            print(path.read_text(encoding='utf-8'))
            raise SystemExit(f'FAIL {name}: {path}')
        print('PASS '+name,flush=True)
    os.environ['SN34_KEYBOARD']=args.keyboard
    from verify_artifacts import verify_build
    print(json.dumps(verify_build(build),indent=2))


if __name__=='__main__':main()
