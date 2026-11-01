# /// script
# dependencies = ["pefile", "pyelftools", "unicorn", "capstone"]
# ///
"""Package a verified target application; OEM updater templates stay external."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zlib
from build_config import ROOT, keyboard_name, board_directory


def sha(data):return hashlib.sha256(data).hexdigest()


def preserve_settings(application, previous, build):
    from storage import LAYOUT, HEADER, read_banks, normalize_via_tag
    records=read_banks(previous)
    if not records:raise ValueError('Backup has no compatible committed settings bank')
    expected=None
    newest=records[0]
    for record in records[1:]:
        distance=(record['sequence']-newest['sequence'])&0xffffffff
        if 0<distance<0x80000000:newest=record
    result=bytearray(application)
    for record in records:
        payload=bytearray(record['payload'])
        normalize_via_tag(payload)
        header=bytearray(record['header'])
        struct.pack_into('<I',header,16,zlib.crc32(payload))
        struct.pack_into('<I',header,24,zlib.crc32(header[:HEADER.size-4]))
        bank=record['bank']
        result[bank:bank+LAYOUT.eeprom_size]=payload
        result[bank+LAYOUT.eeprom_size:bank+LAYOUT.eeprom_bank_size]=header
        if record is newest:expected=bytes(payload)
    # Execute new-firmware startup with these banks and reject any unexpected
    # reset of the preserved cache. No physical device is opened here.
    os.environ['SN34_NATIVE_BUILD']=str(build)
    sys.path.insert(0,str(ROOT/'tests/sn34/common'))
    from keyboard import Keyboard, SYMS
    machine=Keyboard(bytes(result[LAYOUT.code_limit:LAYOUT.eeprom_end]))
    restored=bytes(machine.u.mem_read(SYMS['cache'],LAYOUT.eeprom_size))
    if restored!=expected:
        raise ValueError('New firmware startup changed the preserved settings; an explicit format migration is required')
    return bytes(result),{'backup_sha256':sha(previous),'sequence':newest['sequence'],'banks':len(records)}


def wrap_updater(template, application, contract):
    import pefile
    if sha(template)!=contract['template_sha256']:
        raise ValueError('OEM updater template does not match the selected keyboard contract')
    wrapper=bytearray(template)
    pe=pefile.PE(data=bytes(wrapper))
    resources={item.id:item.directory.entries[0].data.struct
               for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries if ty.id==10
               for item in ty.directory.entries}
    app_resource=resources[contract['application_resource']]
    checksum_resource=resources[contract['checksum_resource']]
    if app_resource.Size!=len(application) or checksum_resource.Size!=8:
        raise ValueError('OEM updater resource sizes do not match the target image/checksum contract')
    offset=pe.get_offset_from_rva(app_resource.OffsetToData)
    wrapper[offset:offset+len(application)]=application
    checksum=sum(struct.unpack(f'<{len(application)//2}H',application))&0xffff
    offset=pe.get_offset_from_rva(checksum_resource.OffsetToData)
    wrapper[offset:offset+8]=f'{checksum:04X}'.encode('utf-16le')
    pe=pefile.PE(data=bytes(wrapper))
    struct.pack_into('<I',wrapper,pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'),pe.generate_checksum())
    check=pefile.PE(data=bytes(wrapper))
    assert check.verify_checksum()
    assert check.get_data(app_resource.OffsetToData,len(application))==application
    return bytes(wrapper),checksum


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=ROOT/'.build/sn34'/keyboard_name()/'default')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--settings-backup',type=Path,help='Compatible full application readback; only settings banks are retained')
    parser.add_argument('--updater-template',type=Path,help='External OEM EXE matching this target; omit for application-only output')
    args=parser.parse_args()
    build=(ROOT/args.build_dir).resolve()
    manifest=json.loads((build/'manifest.json').read_text(encoding='utf-8'))
    os.environ['SN34_KEYBOARD']=manifest['keyboard']
    target=json.loads((board_directory()/'target.json').read_text(encoding='utf-8'))
    if target.get('test_only'):parser.error('Synthetic targets cannot produce release packages')
    from verify_artifacts import verify_build
    verify_build(build)
    application=(build/'application.bin').read_bytes()
    settings=None
    if args.settings_backup:
        application,settings=preserve_settings(application,args.settings_backup.read_bytes(),build)
    output=(ROOT/args.output_dir).resolve() if args.output_dir else build/'release'
    output.mkdir(parents=True,exist_ok=True)
    (output/'application.bin').write_bytes(application)
    record={'keyboard':manifest['keyboard'],'qmk_commit':manifest['qmk_commit'],
            'source_image_sha256':manifest['image_sha256'],'application_sha256':sha(application),
            'hardware_verified':False,'settings':settings,'bootloader':target['bootloader']}
    if args.updater_template:
        if 'updater' not in target:parser.error('Selected target has no OEM updater packaging backend')
        wrapper,checksum=wrap_updater(args.updater_template.read_bytes(),application,target['updater'])
        (output/'updater.exe').write_bytes(wrapper)
        record.update(updater_sha256=sha(wrapper),checksum=f'0x{checksum:04X}')
    (output/'manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
