// SPDX-License-Identifier: GPL-2.0-or-later
// Keyboard policy is linked independently of the selected keymap.
#include "quantum.h"
#include "platform.h"
#include "profile.h"

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_profile(keycode, record)) return false;
    if (keycode == QK_KB_30) {
        if (record->event.pressed) {
            keymap_config.no_gui = !keymap_config.no_gui;
            eeconfig_update_keymap(&keymap_config);
            sn34_eeprom_request_save();
            clear_keyboard();
        }
        return false;
    }
    if (keycode == QK_KB_31) {
        if (record->event.pressed) {
            default_layer_set((default_layer_state & (1u << SN34_MAC_BASE_LAYER)) ?
                              1u << SN34_WIN_BASE_LAYER : 1u << SN34_MAC_BASE_LAYER);
            eeconfig_update_default_layer(default_layer_state);
            sn34_eeprom_request_save();
        }
        return false;
    }
    return process_record_user(keycode, record);
}
