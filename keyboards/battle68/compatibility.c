// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "analog_matrix.h"
#include "eeprom.h"
#include "sn34_eeprom.h"

bool sn34_eeprom_migrate(void) {
    // v3 restores v1's separate profile byte. Only Battle68 v2 needs its
    // calibration and following VIA bytes shifted; leave committed banks intact.
    if (sn34_eeprom_version() != 2) return true;
    uint8_t tail[2], selected, chunk[64];
    eeprom_read_block(tail, (void *)(EEPROM_SIZE - 2), sizeof(tail));
    // v2 had one extra macro byte. Refuse to truncate a full/unfinished buffer.
    if (tail[0] || tail[1]) return false;
    eeprom_read_block(&selected, (void *)(EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CURRENT_PROFILE), 1);
    unsigned start = EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CALIBRATED_DATA_START - 1;
    for (unsigned end = EEPROM_SIZE - 1; end > start;) {
        unsigned size = end - start;
        if (size > sizeof(chunk)) size = sizeof(chunk);
        end -= size;
        eeprom_read_block(chunk, (void *)(uintptr_t)end, size);
        eeprom_update_block(chunk, (void *)(uintptr_t)(end + 1), size);
    }
    eeprom_update_byte((uint8_t *)(EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CURRENT_PROFILE), selected);
    return true;
}
