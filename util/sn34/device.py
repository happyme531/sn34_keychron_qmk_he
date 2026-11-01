# /// script
# dependencies = ["hidapi"]
# ///
"""Configure an SN34 keyboard selected by model and, optionally, USB serial."""
import argparse
import os
import sys


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--keyboard',default=os.environ.get('SN34_KEYBOARD','battle68'))
    parser.add_argument('--serial',default=os.environ.get('SN34_DEVICE_SERIAL'))
    args,remaining=parser.parse_known_args()
    os.environ['SN34_KEYBOARD']=args.keyboard
    if args.serial:os.environ['SN34_DEVICE_SERIAL']=args.serial
    from build_config import keyboard_name
    keyboard_name()
    import device_commands
    sys.argv=[device_commands.__file__,*remaining]
    device_commands.main()


if __name__=='__main__':main()
