"""Independent persistent-format fixture reader for offline and backup tests."""
from dataclasses import dataclass, replace
import json
import struct
import zlib
from datetime import datetime
from target import ROOT, board_directory

STORAGE_FILE = board_directory() / "storage.json"
HEADER = struct.Struct("<7I")


@dataclass(frozen=True)
class StorageLayout:
    schema_version: int
    app_origin: int
    app_size: int
    page_size: int
    boot_user_offset: int
    eeprom_banks: tuple
    eeprom_bank_size: int
    eeprom_size: int
    eeprom_base: int
    eeprom_magic: int
    eeprom_commit: int
    eeprom_version: int
    legacy_keymap_pages: tuple
    footer_page: int
    footer_address: int
    footer_magic: int
    ram_origin: int
    ram_size: int
    bss_limit: int
    he: dict
    rgb_core_offset: int
    rgb_value_offset: int
    via_eeprom_date: str

    @property
    def stack_top(self):
        return self.ram_origin + self.ram_size

    @property
    def eeprom_end(self):
        return max(self.eeprom_banks) + self.eeprom_bank_size

    @property
    def code_limit(self):
        return min(self.eeprom_banks)

    @property
    def via_magic_offset(self):
        return self.eeprom_base + self.he["size"]

    @property
    def via_magic(self):
        return bytes.fromhex(datetime.strptime(self.via_eeprom_date, "%Y-%m-%d-%H:%M:%S").strftime("%y%m%d"))


def load_storage(path=None):
    data = json.loads((path or board_directory() / "storage.json").read_text(encoding="utf-8"))
    number = lambda value: int(value, 0) if isinstance(value, str) else value
    for name, value in list(data.items()):
        if name == "via_eeprom_date":
            continue
        data[name] = tuple(map(number, value)) if isinstance(value, list) else number(value)
    data["he"] = {name: number(value) for name, value in data["he"].items()}
    layout = StorageLayout(**data)
    datetime.strptime(layout.via_eeprom_date, "%Y-%m-%d-%H:%M:%S")
    regions = [(bank, bank + layout.eeprom_bank_size) for bank in layout.eeprom_banks]
    if (layout.schema_version != 1 or len(regions) != 2 or layout.page_size <= 0 or layout.page_size & (layout.page_size - 1)
            or layout.eeprom_size + layout.page_size != layout.eeprom_bank_size
            or layout.eeprom_size % layout.page_size or HEADER.size > layout.page_size):
        raise ValueError("Invalid EEPROM bank/page contract")
    if any(start % layout.page_size or end > layout.footer_page for start, end in regions):
        raise ValueError("EEPROM bank overlaps reserved footer or is misaligned")
    if max(regions[0][0], regions[1][0]) < min(regions[0][1], regions[1][1]):
        raise ValueError("EEPROM banks overlap")
    if (layout.footer_page % layout.page_size or layout.footer_address != layout.app_size - 4
            or layout.footer_page + layout.page_size != layout.app_size
            or not layout.ram_origin < layout.bss_limit < layout.stack_top
            or layout.eeprom_base + layout.he["size"] > layout.eeprom_size):
        raise ValueError("Invalid application, RAM or HE storage bounds")
    return layout


LEGACY_LAYOUT = load_storage()
LAYOUT = replace(LEGACY_LAYOUT, eeprom_version=3)


def read_banks(image, layout=LAYOUT):
    if len(image) != layout.app_size:
        raise ValueError("Backup is not a complete application image")
    records = []
    for bank in layout.eeprom_banks:
        payload = bytes(image[bank:bank + layout.eeprom_size])
        header = bytes(image[bank + layout.eeprom_size:bank + layout.eeprom_bank_size])
        magic, version, sequence, size, crc, commit, header_crc = HEADER.unpack_from(header)
        if ((magic, size, commit) == (layout.eeprom_magic, layout.eeprom_size, layout.eeprom_commit)
                and version in (1, 2, 3) and version <= layout.eeprom_version
                and zlib.crc32(payload) == crc and zlib.crc32(header[:HEADER.size - 4]) == header_crc):
            records.append({"bank": bank, "sequence": sequence, "version": version, "payload": payload, "header": header})
    return records


def normalize_via_tag(payload, layout=LAYOUT):
    """Keep valid old VIA data while replacing its former build-date tag."""
    offset=layout.via_magic_offset
    previous=bytes(payload[offset:offset+3])
    # An invalid/erased VIA tag means the firmware intended a reset. Do not
    # accidentally turn that state back into a valid old keymap/macro buffer.
    if len(previous)!=3:
        raise ValueError("Missing VIA compatibility tag")
    try:
        datetime.strptime("20"+previous.hex(), "%Y%m%d")
    except ValueError as exc:
        raise ValueError("Backup VIA data is invalid or explicitly marked for reset") from exc
    payload[offset:offset+3]=layout.via_magic
    return previous
