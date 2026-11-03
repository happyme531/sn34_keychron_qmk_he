"""CRC-protected SN34 EEPROM banks, independent of tests and host emulation."""
import struct
import zlib

HEADER = struct.Struct('<7I')


def newest_bank(records):
    result = records[0]
    for item in records[1:]:
        if 0 < (item['sequence'] - result['sequence']) & 0xffffffff < 0x80000000:
            result = item
    return result


def read_banks(image, memory):
    if memory['app_origin'] != 0:
        raise ValueError('SN34F280 application must start at User-ROM offset zero')
    if len(image) != memory['app_size']:
        raise ValueError('Backup is not a complete application image')
    size = memory['eeprom_size']
    records = []
    for bank in (memory['eeprom_bank0'], memory['eeprom_bank1']):
        payload = bytes(image[bank:bank + size])
        header = bytes(image[bank + size:bank + memory['eeprom_bank_size']])
        magic, version, sequence, stored_size, crc, commit, header_crc = HEADER.unpack_from(header)
        if ((magic, stored_size, commit) == (memory['eeprom_magic'], size, memory['eeprom_commit'])
                and version == memory['eeprom_version']
                and zlib.crc32(payload) == crc
                and zlib.crc32(header[:HEADER.size - 4]) == header_crc):
            records.append(dict(bank=bank, version=version, sequence=sequence, payload=payload, header=header))
    return records


def snapshot_image(payload, memory):
    """Wrap a live settings cache in a CRC-protected bank, with no firmware code."""
    if memory['app_origin'] != 0:
        raise ValueError('SN34F280 application must start at User-ROM offset zero')
    if len(payload) != memory['eeprom_size']:
        raise ValueError('Settings snapshot size does not match the target')
    header = HEADER.pack(memory['eeprom_magic'], memory['eeprom_version'], 1,
                         len(payload), zlib.crc32(payload), memory['eeprom_commit'], 0)
    header = header[:-4] + struct.pack('<I', zlib.crc32(header[:-4]))
    image = bytearray(memory['app_size'])
    bank = memory['eeprom_bank0'] - memory['app_origin']
    image[bank:bank + len(payload)] = payload
    image[bank + len(payload):bank + len(payload) + len(header)] = header
    return bytes(image)
