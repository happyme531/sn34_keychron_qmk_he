# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Validate a one-shot RAM recovery callback on the exact installed v20 image.
The SDK's unbounded vendor OUT buffer permits reaching SetVendor_cb within the
same USBD handle. Preserve its initialized tail and redirect only that callback
to the existing bootloader_jump hook; do not upload any executable code.
"""
import os
os.environ["BAT68_NATIVE_BUILD"]="build/bat68_v20_repro"
import hashlib
import json
import struct
from test_bat68 import Keyboard,BUILD,IMAGE,SYMS,ROOT
from elftools.elf.elffile import ELFFile

expected="cd8f0e26dcfdd2e78eafff21410e67eca3a041022d37059c73472957d403b049"
assert hashlib.sha256(IMAGE).hexdigest()==expected
with (BUILD/"native_usb.elf").open("rb") as stream:
    elf=ELFFile(stream)
    device_symbol=next(s for s in elf.get_section_by_name(".symtab").iter_symbols() if s.name=="device")
    size=device_symbol["st_size"]
m=Keyboard();m.call("USBD_Reset",SYMS["device"]);assert m.setup(0,5,7)==0
assert m.setup(0x40,0x5a,0,0,1)==0
ep,buffer,length=m.receives[-1];assert ep==0 and length==1
offset=buffer-SYMS["device"]
original=bytes(m.u.mem_read(SYMS["device"],size))
needle=struct.pack("<I",SYMS["bat68_xinput_vendor"])
assert original.count(needle)==1
get_callback=original.index(needle);set_callback=get_callback+4
length=set_callback+4-offset
assert 2048<length<4096 and set_callback+4<=size
assert m.setup(0x40,0x5a,0,0,length)==0
payload=bytearray(m.u.mem_read(buffer,length))
struct.pack_into("<I",payload,set_callback-offset,SYMS["bootloader_jump"])
before=bytes(m.u.mem_read(SYMS["device"]+offset+2048,length-2048))
m.u.mem_write(buffer,bytes(payload));m.call("HAL_PCD_DataOutStageCallback",0,0)
assert m.u.mem_read(SYMS["native_boot_requested"],1)==b"\x01"
assert m.u.mem_read(SYMS["native_restart_requested"],1)==b"\0"
# The only changed byte range in the structural tail is the callback itself.
after=bytes(payload[2048:]);assert before[:-4]==after[:-4]
path=BUILD/"ram_recovery.bin";path.write_bytes(payload)
result=dict(status="PASS_OFFLINE_RAM_RECOVERY",installed_image_sha256=expected,
    payload_bytes=length,payload_sha256=hashlib.sha256(payload).hexdigest(),payload=path.relative_to(ROOT).as_posix(),
    device_address=hex(SYMS["device"]),device_bytes=size,request_buffer_offset=offset,
    callback_address=hex(SYMS["device"]+set_callback),existing_boot_hook=hex(SYMS["bootloader_jump"]),
    uploaded_executable_code=False,flash_commands_in_payload=False,
    effect="Invoke existing bootloader_jump to request the firmware's normal retained-Boot entry")
(BUILD/"ram_recovery_test.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
