"""CRC-protected SN34 EEPROM banks, independent of tests and host emulation."""
import struct
import zlib

HEADER = struct.Struct('<7I')


def read_banks(image, memory):
    if len(image) != memory['app_size']:
        raise ValueError('Backup is not a complete application image')
    size = memory['eeprom_size']
    records = []
    for bank in (memory['eeprom_bank0'], memory['eeprom_bank1']):
        payload = bytes(image[bank:bank + size])
        header = bytes(image[bank + size:bank + memory['eeprom_bank_size']])
        magic, version, sequence, stored_size, crc, commit, header_crc = HEADER.unpack_from(header)
        if ((magic, stored_size, commit) == (memory['eeprom_magic'], size, memory['eeprom_commit'])
                and version in (1, memory['eeprom_version'])
                and zlib.crc32(payload) == crc
                and zlib.crc32(header[:HEADER.size - 4]) == header_crc):
            records.append(dict(bank=bank, version=version, sequence=sequence, payload=payload, header=header))
    return records
