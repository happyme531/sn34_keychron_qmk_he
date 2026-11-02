// SPDX-License-Identifier: GPL-2.0-or-later
// Keychron's calibration storage interface, independent of Flash bank commits.
#include "quantum.h"
#include "analog_matrix.h"
#include "eeprom.h"
#include "sn34_eeprom.h"
#include "sn34_board.h"
#include "sn34_calibration.h"
#include "nvm_eeprom_eeconfig_internal.h"
static uint8_t external[EXTERNAL_EEPROM_OFFSET + OFFSET_CALIBRATED_DATA_END];
_Static_assert((uintptr_t)EECONFIG_KB_DATABLOCK == SN34_EEPROM_BASE, "QMK core EEPROM layout changed");
_Static_assert(sizeof(calibrated_value_t)==SIZE_OF_CALIB_VALUE_T,"Keychron calibration layout");
_Static_assert(EECONFIG_BASE_ANALOG_MATRIX+EECONFIG_SIZE_ANALOG_MATRIX<=EEPROM_SIZE,"EEPROM fits bank");

static void migrate_v1_settings(void) {
    // v1 inserted one byte before calibration. Restore the stock HE layout and
    // move all following VIA/keymap/macro bytes with it. The old bank stays valid
    // until the ordinary two-bank engine commits a v2 image.
    if (sn34_eeprom_version() != 1) return;
    uint8_t selected, chunk[64];
    eeprom_read_block(&selected, (void *)(EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CURRENT_PROFILE), 1);
    for (unsigned at = EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CALIBRATED_DATA_START + 1; at < EEPROM_SIZE;) {
        unsigned size = EEPROM_SIZE - at;
        if (size > sizeof(chunk)) size = sizeof(chunk);
        eeprom_read_block(chunk, (void *)(uintptr_t)at, size);
        eeprom_update_block(chunk, (void *)(uintptr_t)(at - 1), size);
        at += size;
    }
    eeprom_update_byte((uint8_t *)(EEPROM_SIZE - 1), 0);
    // Stock storage shares this byte with the first calibration record.
    eeprom_update_byte((uint8_t *)(EECONFIG_BASE_ANALOG_MATRIX + OFFSET_CURRENT_PROFILE), selected);
}
__attribute__((weak)) bool sn34_board_calibration_read(void *buffer,size_t size){
    (void)buffer;(void)size;return false;
}
void sn34_he_calibration_init(void){
    migrate_v1_settings();
    memset(external,0,sizeof(external));
    if(sn34_board_calibration_read(external,sizeof(external)))return;
    // The selected board supplies the fallback endpoints and their provenance.
    uint32_t vendor = VENDOR_ID; memcpy(external, &vendor, 4);
    external[4 + OFFSET_CALIBRATION] = 1; // Released references known; bottom still estimated.
    calibrated_value_t *values = (calibrated_value_t *)(external + 4 + OFFSET_CALIBRATED_DATA_START);
    for (unsigned i = 0; i < SN34_KEY_COUNT; i++) {
        values[board_keys[i].matrix_slot].zero_travel = board_keys[i].idle;
        values[board_keys[i].matrix_slot].full_travel = board_keys[i].bottom;
    }
}
void he_eeprom_driver_init(void) {}
void he_eeprom_driver_erase(void) { memset(external, 0, sizeof(external)); }
void he_eeprom_read_block(void *dst, const void *src, size_t size) {
    uintptr_t offset = (uintptr_t)src;
    if (offset <= sizeof(external) && size <= sizeof(external) - offset) memcpy(dst, external + offset, size);
    else memset(dst, 0, size);
}
void he_eeprom_write_block(const void *src, void *dst, size_t size) {
    uintptr_t offset = (uintptr_t)dst;
    if (offset <= sizeof(external) && size <= sizeof(external) - offset) memcpy(external + offset, src, size);
}
