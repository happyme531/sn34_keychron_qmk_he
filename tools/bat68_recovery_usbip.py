"""Local USB/IP recovery of BAT68 EP0 without selecting any configuration.
Uses the already-authorized device-specific usbipd binding at bus 4-4.
Reads descriptors and optionally sends the existing OTA-entry Feature only.
Protocol reference: https://docs.kernel.org/usb/usbip_protocol.html
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import hashlib
import time

ROOT=Path(__file__).resolve().parents[1]


def receive(sock,size):
    data=bytearray()
    while len(data)<size:
        part=sock.recv(size-len(data))
        if not part:raise ConnectionError("USB/IP connection closed")
        data.extend(part)
    return bytes(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enter-boot",action="store_true")
    parser.add_argument("--ram-recovery",action="store_true",help="Use the separately emulated, exact-v20 RAM callback recovery")
    args=parser.parse_args();result=dict(busid="4-4",configuration_selected=False,entry_requested=args.enter_boot)
    try:
        with socket.create_connection(("127.0.0.1",3240),timeout=5) as sock:
            sock.settimeout(15) # A failed composite driver may need time to release its PDO.
            sock.sendall(struct.pack("!HHI",0x0111,0x8003,0)+b"4-4"+bytes(29))
            version,reply,status=struct.unpack("!HHI",receive(sock,8))
            assert version==0x0111 and reply==3 and status==0,(version,reply,status)
            device=receive(sock,312)
            bus,number,speed,vid,pid,rev=struct.unpack_from("!IIIHHH",device,288)
            assert (vid,pid)==(0x0c45,0x8037),(vid,pid)
            result.update(vid=hex(vid),pid=hex(pid),speed=speed,revision=hex(rev))
            sequence=0;devid=(bus<<16)|number
            def control(request_type,request,value,index,size,payload=b"",allow_stall=False):
                nonlocal sequence
                sequence+=1;direction=request_type>>7
                setup=struct.pack("<BBHHH",request_type,request,value,index,size)
                header=struct.pack("!10I",1,sequence,devid,direction,0,0,size,0,0xffffffff,0)+setup
                sock.sendall(header+(payload if not direction else b""))
                reply=receive(sock,48)
                command,seq=struct.unpack_from("!II",reply)
                status,length=struct.unpack_from("!ii",reply,20)
                assert command==3 and seq==sequence,(command,seq,sequence)
                result.setdefault("transfers",[]).append(dict(request_type=hex(request_type),request=request,index=index,status=status,length=length))
                data=receive(sock,length) if direction and length>0 else b""
                assert status==0 or (allow_stall and status in (-32,-19,-104)),("USB/IP transfer failed",status)
                return data,length
            config,_=control(0x80,6,0x0200,0,512)
            assert config[:2]==bytes((9,2))
            result["configuration_hex"]=config.hex()
            if args.ram_recovery:
                assert args.enter_boot
                folder=ROOT/"build/bat68_v20_repro"
                proof=json.loads((folder/"ram_recovery_test.json").read_text())
                payload=(folder/"ram_recovery.bin").read_bytes()
                assert proof["status"]=="PASS_OFFLINE_RAM_RECOVERY"
                assert proof["installed_image_sha256"]=="cd8f0e26dcfdd2e78eafff21410e67eca3a041022d37059c73472957d403b049"
                assert len(payload)==proof["payload_bytes"]==2156
                assert hashlib.sha256(payload).hexdigest()==proof["payload_sha256"]
                recorded=json.loads((ROOT/"analysis/bat68_recovery_control.json").read_text())
                assert config.hex()==recorded["configuration_hex"] and rev==0x0200
                result["ram_recovery_proof"]=proof
                try:control(0x40,0x5a,0,0,len(payload),payload,allow_stall=True)
                except ConnectionError:result["entry_connection_closed"]=True
                # Give the normal main-loop boot hook time to invalidate its
                # footer and reboot before USB/IP releases the physical port.
                time.sleep(0.4)
                result["entry_sent_hardware_boot_confirmation_required"]=True
            elif args.enter_boot:
                _,length=control(0x21,9,0x0300,3,64,bytes.fromhex("aa55a55aff0033cc")+bytes(56))
                result["entry_bytes_sent"]=length
    except Exception as exc:
        result["error"]=str(exc);raise
    finally:
        (ROOT/"analysis/bat68_recovery_usbip.json").write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))


if __name__=="__main__":main()
