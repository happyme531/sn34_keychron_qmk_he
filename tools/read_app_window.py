# /// script
# dependencies = ["hidapi"]
# ///
"""Read-only stock command 0x11, bounded to its 16-bit offset ROM window.

Does not send 0x10 (which has a persistent side effect), write commands, or ISP
entry. Native HID calls run in a child process so Windows cannot hang the host.
The window is partial application data, never a complete firmware backup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

BASE = 0x9200

def integer(value):
    return int(value, 0)

def worker(args):
    import hid
    matches = [d for d in hid.enumerate(0x0c45, 0x8037)
               if d["interface_number"] == 2 and d["usage_page"] == 0xff68
               and d["product_string"] == "EWEADN BAT68"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one responding BAT68 interface, found {len(matches)}")
    dev = hid.device()
    dev.open_path(matches[0]["path"])
    result = bytearray()
    print(json.dumps({"action":"begin", "start":hex(args.start), "length":args.length,
                      "usb_version":hex(matches[0]["release_number"])}), flush=True)
    def query(at, count):
            packet = bytearray(64)
            packet[:3] = bytes((0xaa, 0x11, count))
            struct.pack_into("<H", packet, 3, at-BASE)
            packet[5:8] = b"R11"
            for _ in range(16):
                if not dev.read(64, 1):
                    break
            n = dev.write(b"\0"+packet)
            if n != 65:
                raise RuntimeError(f"Short HID write: {n}")
            deadline = time.monotonic()+1
            while time.monotonic() < deadline:
                reply = bytes(dev.read(64, 30))
                if len(reply) == 65 and reply[0] == 0:
                    reply = reply[1:]
                if len(reply) == 64 and reply[:8] == b"\x55"+packet[1:8]:
                    return reply[8:8+count]
            else:
                raise TimeoutError(f"No reply for offset {at-BASE:#x}")
    try:
        stride = 56-args.prefix
        for at in range(args.start, args.start+args.length, stride):
            count = min(stride, args.start+args.length-at)
            # Stock v1.18 overwrites response payload bytes 1 and 6 with
            # settings metadata after copying ROM. Skip a leading eight bytes.
            if at >= BASE+args.prefix:
                data = query(at-args.prefix, count+args.prefix)[args.prefix:]
            else:
                data = bytearray(query(at, count))
                for offset in (1, 6):
                    if offset < count:
                        data[offset] = query(at+offset, 1)[0]
            result.extend(data)
        args.output.write_bytes(result)
        print(json.dumps({"bytes":len(result),"sha256":hashlib.sha256(result).hexdigest(),
                          "head":result[:64].hex(),"output":str(args.output)}), flush=True)
    finally:
        dev.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=integer, required=True)
    p.add_argument("--length", type=integer, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prefix", type=int, choices=(8,16), default=8,
                   help="Leading response bytes to discard; 16 verifies with different request alignment")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.length <= 0 or args.start < BASE or args.start+args.length > BASE+0x10000:
        p.error("Read must stay within 0x9200..0x191ff, with positive length")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.worker:
        worker(args)
        return
    cmd = [sys.executable, "-u", __file__, *sys.argv[1:], "--worker"]
    timeout = min(60, max(8, args.length/(56-args.prefix)*0.04+5))
    try:
        result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired as e:
        print(e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else e.stdout or "")
        raise SystemExit("HID helper timed out and was terminated; no other device commands sent")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    raise SystemExit(result.returncode)

if __name__ == "__main__":
    main()
