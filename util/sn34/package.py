# /// script
# dependencies = ["pefile", "pyelftools"]
# ///
"""Package a standard SN34 QMK ELF; OEM updater templates stay external."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
from firmware import Firmware, ROOT, keyboard_definition, keyboard_file
from settings import read_banks, newest_bank, migrated_payload


def sha(data):return hashlib.sha256(data).hexdigest()


def preserve_settings(application, previous, firmware):
    memory=firmware.memory
    records=read_banks(previous,memory)
    if not records:raise ValueError('Backup has no compatible committed settings bank')
    newest=newest_bank(records)
    migrated_payload(newest, memory)  # Check legacy migration before writing any output.
    result=bytearray(application)
    for record in records:
        bank=record['bank']
        result[bank:bank+memory['eeprom_size']]=record['payload']
        result[bank+memory['eeprom_size']:bank+memory['eeprom_bank_size']]=record['header']
    # Keep committed banks intact; firmware handles versioned layout migration.
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
    parser.add_argument('elf',type=Path)
    parser.add_argument('--keyboard',default='battle68')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--settings-backup',type=Path,help='Compatible full application readback; only settings banks are retained')
    parser.add_argument('--updater-template',type=Path,help='External OEM EXE matching this target; omit for application-only output')
    args=parser.parse_args()
    os.environ['SN34_KEYBOARD']=args.keyboard
    keyboard_definition(args.keyboard)
    firmware=Firmware(args.elf)
    firmware.validate_keyboard(args.keyboard)
    application=firmware.application()
    settings=None
    if args.settings_backup:
        application,settings=preserve_settings(application,args.settings_backup.read_bytes(),firmware)
    output=(ROOT/args.output_dir).resolve() if args.output_dir else firmware.path.parent/(firmware.path.stem+'_release')
    output.mkdir(parents=True,exist_ok=True)
    (output/'application.bin').write_bytes(application)
    record={'keyboard':args.keyboard,
            'source_image_sha256':sha(firmware.code),'application_sha256':sha(application),
            'hardware_verified':False,'settings':settings,'bootloader':'custom'}
    if args.updater_template:
        try:
            target_path=keyboard_file('board/updater.json', args.keyboard)
        except FileNotFoundError:
            parser.error('Selected keyboard has no OEM updater contract')
        target=json.loads(target_path.read_text(encoding='utf-8'))
        wrapper,checksum=wrap_updater(args.updater_template.read_bytes(),application,target)
        (output/'updater.exe').write_bytes(wrapper)
        record.update(updater_sha256=sha(wrapper),checksum=f'0x{checksum:04X}')
    (output/'manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
