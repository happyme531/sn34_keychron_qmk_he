"""WSL recovery through libusb EP0 without selecting the broken configuration.
Only standard descriptor reads and the existing OTA-entry Feature are allowed.
No flash write/erase/program commands are implemented in this host tool.
"""
import argparse
import ctypes as c
import ctypes.util
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--enter-boot",action="store_true")
    args=p.parse_args()
    lib=c.CDLL(ctypes.util.find_library("usb-1.0"))
    lib.libusb_init.argtypes=[c.POINTER(c.c_void_p)];lib.libusb_init.restype=c.c_int
    lib.libusb_open_device_with_vid_pid.argtypes=[c.c_void_p,c.c_uint16,c.c_uint16]
    lib.libusb_open_device_with_vid_pid.restype=c.c_void_p
    lib.libusb_control_transfer.argtypes=[c.c_void_p,c.c_uint8,c.c_uint8,c.c_uint16,c.c_uint16,c.c_void_p,c.c_uint16,c.c_uint]
    lib.libusb_control_transfer.restype=c.c_int
    lib.libusb_close.argtypes=[c.c_void_p];lib.libusb_exit.argtypes=[c.c_void_p]
    ctx=c.c_void_p();assert lib.libusb_init(c.byref(ctx))==0
    handle=lib.libusb_open_device_with_vid_pid(ctx,0x0c45,0x8037)
    if not handle:raise RuntimeError("Cannot open the attached BAT68 application device")
    result=dict(usb_vid="0x0c45",usb_pid="0x8037",configuration_selected=False,enter_boot_requested=args.enter_boot)
    try:
        data=(c.c_ubyte*512)()
        count=lib.libusb_control_transfer(handle,0x80,6,0x0200,0,data,512,1500)
        assert count>=9,("configuration read",count)
        config=bytes(data[:count]);result["configuration_hex"]=config.hex()
        result["interface_count"]=config[4];endpoints=[];at=0
        while at<len(config):
            length,kind=config[at:at+2];assert length>=2
            if kind==5:endpoints.append(hex(config[at+2]))
            at+=length
        result["endpoints"]=endpoints
        if args.enter_boot:
            # The firmware handles this before SET_CONFIGURATION; the failed
            # FIFO allocation otherwise prevents Windows exposing any HIDs.
            feature=(c.c_ubyte*64).from_buffer_copy(bytes.fromhex("aa55a55aff0033cc")+bytes(56))
            sent=lib.libusb_control_transfer(handle,0x21,9,0x0300,3,feature,64,2000)
            result["entry_transfer_result"]=sent
            assert sent in (64,-4),("entry feature",sent)
    finally:
        lib.libusb_close(handle);lib.libusb_exit(ctx)
        (Path(__file__).resolve().parents[1]/"analysis/bat68_recovery_control.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
