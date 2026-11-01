// SPDX-License-Identifier: GPL-2.0-or-later
// Keychron's calibration storage interface, independent of Flash bank commits.
#include "quantum.h"
#include "analog_matrix.h"
#include "sn34_eeprom.h"
#include "hall.generated.h"
#include "sn34_calibration.h"
#include "nvm_eeprom_eeconfig_internal.h"
static uint8_t external[EXTERNAL_EEPROM_OFFSET + OFFSET_CALIBRATED_DATA_END];
_Static_assert((uintptr_t)EECONFIG_KB_DATABLOCK == SN34_EEPROM_BASE, "QMK core EEPROM layout changed");
#ifdef RGB_MATRIX_ENABLE
_Static_assert((uintptr_t)EECONFIG_RGB_MATRIX == SN34_RGB_CORE_OFFSET, "QMK RGB EEPROM offset changed");
_Static_assert((uintptr_t)EECONFIG_RGB_MATRIX + offsetof(rgb_config_t, hsv.v) == SN34_RGB_VALUE_OFFSET, "QMK RGB value offset changed");
#endif
_Static_assert(KC_ANALOG_MATRIX_VERSION == SN34_HE_VERSION, "Keychron HE ABI changed");
_Static_assert(OFFSET_CALIBRATED_DATA_START == SN34_HE_CALIBRATION_OFFSET, "Calibration ABI changed");
_Static_assert(OFFSET_PROFILES_START == SN34_HE_PROFILES_OFFSET && PROFILE_SIZE == SN34_HE_PROFILE_SIZE, "Profile ABI changed");
_Static_assert(OFFSET_CURVE_PTS_START == SN34_HE_CURVE_OFFSET, "Curve ABI changed");
_Static_assert(OFFSET_GAME_CONTROLLER_MODE_START == SN34_HE_CONTROLLER_OFFSET && EECONFIG_SIZE_ANALOG_MATRIX == SN34_HE_SIZE, "HE storage size changed");

_Static_assert(sizeof(calibrated_value_t)==SIZE_OF_CALIB_VALUE_T,"Keychron calibration layout");
_Static_assert(EECONFIG_BASE_ANALOG_MATRIX+EECONFIG_SIZE_ANALOG_MATRIX<=EEPROM_SIZE,"EEPROM fits bank");
__attribute__((weak)) bool sn34_board_calibration_read(void *buffer,size_t size){
    (void)buffer;(void)size;return false;
}
void sn34_he_calibration_init(void){
    memset(external,0,sizeof(external));
    if(sn34_board_calibration_read(external,sizeof(external)))return;
    // The selected board supplies the fallback endpoints and their provenance.
    uint32_t vendor = VENDOR_ID; memcpy(external, &vendor, 4);
    external[4 + OFFSET_CALIBRATION] = 1; // Released references known; bottom still estimated.
    calibrated_value_t *values = (calibrated_value_t *)(external + 4 + OFFSET_CALIBRATED_DATA_START);
    for (unsigned i = 0; i < SN34_HALL_KEYS; i++) {
        values[hall_keys[i].slot].zero_travel = hall_keys[i].idle;
        values[hall_keys[i].slot].full_travel = hall_keys[i].bottom;
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
