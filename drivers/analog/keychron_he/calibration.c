// SPDX-License-Identifier: GPL-2.0-or-later
// Keychron's calibration storage interface, independent of Flash bank commits.
#include "quantum.h"
#include "analog_matrix.h"
#include "eeprom.h"
#include "sn34_board.h"
#include "sn34_he.h"
#include "nvm_eeprom_eeconfig_internal.h"
static uint8_t external[EXTERNAL_EEPROM_OFFSET + OFFSET_CALIBRATED_DATA_END];
_Static_assert((uintptr_t)EECONFIG_KB_DATABLOCK == SN34_EEPROM_BASE, "QMK core EEPROM layout changed");
_Static_assert(sizeof(calibrated_value_t)==SIZE_OF_CALIB_VALUE_T,"Keychron calibration layout");
_Static_assert(EECONFIG_BASE_ANALOG_MATRIX+EECONFIG_SIZE_ANALOG_MATRIX<=EEPROM_SIZE,"EEPROM fits bank");
_Static_assert(OFFSET_CALIBRATED_DATA_START > OFFSET_CURRENT_PROFILE, "Profile must not overlap calibration");

void sn34_he_calibration_init(void){
    memset(external,0,sizeof(external));
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
