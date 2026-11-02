// SPDX-License-Identifier: GPL-2.0-or-later
// Keyboard policy is linked independently of the selected keymap.
#include "quantum.h"
#include "sn34.h"
#include "sn34_eeprom.h"
#include "sn34_he.h"
#include "profile.h"
#include "analog_matrix.h"

void sn34_indicators_task(void);
void housekeeping_task_kb(void) {
    if (sn34_host_ready()) process_profile_select_combo();
    sn34_indicators_task();
    sn34_eeprom_task(sn34_he_idle());
}

#ifdef RGB_MATRIX_ENABLE
bool rgb_matrix_indicators_kb(void) {
    analog_matrix_indicator();
    return rgb_matrix_indicators_user();
}
#endif

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_profile(keycode, record)) return false;
    if (keycode == QK_KB_30) {
        if (record->event.pressed) {
            keymap_config.no_gui = !keymap_config.no_gui;
            eeconfig_update_keymap(&keymap_config);
            clear_keyboard();
        }
        return false;
    }
    if (keycode == QK_KB_31) {
        if (record->event.pressed) {
            default_layer_set((default_layer_state & (1u << SN34_MAC_BASE_LAYER)) ?
                              1u << SN34_WIN_BASE_LAYER : 1u << SN34_MAC_BASE_LAYER);
            eeconfig_update_default_layer(default_layer_state);
        }
        return false;
    }
    return process_record_user(keycode, record);
}
