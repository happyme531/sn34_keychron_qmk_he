# /// script
# dependencies = []
# ///
"""Run SN34 tools with locked dependencies and separate Windows/Linux environments."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__,add_help=False)
    parser.add_argument('command',choices=('build','test','device','package'))
    if len(sys.argv)==1 or sys.argv[1] in ('-h','--help'):
        parser.print_help();return
    args,remaining=parser.parse_known_args()
    scripts={'build':'build.py','test':'check.py','device':'device.py','package':'package.py'}
    root=Path(__file__).resolve().parents[2]
    env=dict(os.environ)
    env.pop('VIRTUAL_ENV',None)
    env['UV_PROJECT_ENVIRONMENT']=str(root/'.build/python'/('windows' if os.name=='nt' else 'linux'))
    result=subprocess.run(['uv','run','--project',str(root/'util/sn34'),'--locked','python',
                           str(root/'util/sn34'/scripts[args.command]),*remaining],cwd=root,env=env)
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
