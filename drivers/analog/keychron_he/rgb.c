// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "eeconfig_kb.h"
#include "keychron_rgb_type.h"
#include "rgb_protocol.h"
#include "eeprom.h"

// The rendering and configuration protocol are Keychron's shared implementation.
HSV default_per_key_led[RGB_MATRIX_LED_COUNT] = {[0 ... RGB_MATRIX_LED_COUNT - 1] = {0, 255, 255}};
uint8_t default_region[RGB_MATRIX_LED_COUNT] = {
#ifdef SN34_RGB_ZONE2_START
    [SN34_RGB_ZONE2_START ... RGB_MATRIX_LED_COUNT - 1] = 1,
#endif
};
uint8_t retail_demo_enable;

_Static_assert(EECONFIG_END_CUSTOM_RGB <= EEPROM_SIZE, "HE and custom RGB must fit EEPROM");
_Static_assert(EECONFIG_SIZE_CUSTOM_RGB + sizeof(uint32_t) <= SN34_CUSTOM_RGB_STORAGE_SIZE, "Reserve space for custom RGB and its version in the board EEPROM layout");

#define SN34_RGB_CONFIG_MAGIC 0x52474201u
#define SN34_RGB_CONFIG_VERSION ((uint32_t *)(EECONFIG_BASE_ANALOG_MATRIX + EECONFIG_KB_DATA_SIZE - sizeof(uint32_t)))

uint8_t keychron_rgb_effect_to_wire(uint8_t effect) {
    return effect < sizeof(sn34_rgb_core_to_wire) ? sn34_rgb_core_to_wire[effect] : 255;
}

uint8_t keychron_rgb_effect_from_wire(uint8_t effect) {
    return effect < sizeof(sn34_rgb_wire_to_core) ? sn34_rgb_wire_to_core[effect] : 255;
}

void eeconfig_reset_custom_rgb(void);
void eeconfig_init_custom_rgb(void);

void eeconfig_init_kb_datablock(void) {
    eeconfig_reset_custom_rgb();
    eeprom_update_dword(SN34_RGB_CONFIG_VERSION, SN34_RGB_CONFIG_MAGIC);
}

void keyboard_post_init_kb(void) {
    // A fresh build with RGB disabled leaves its reserved block empty. Enabling
    // RGB later initializes that block without resetting HE, keymaps or macros.
    if (eeprom_read_dword(SN34_RGB_CONFIG_VERSION) != SN34_RGB_CONFIG_MAGIC) eeconfig_init_kb_datablock();
    eeconfig_init_custom_rgb();
    keyboard_post_init_user();
}
