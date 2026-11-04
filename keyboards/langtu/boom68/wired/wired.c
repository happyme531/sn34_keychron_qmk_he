// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34f28x_hal.h"
#include "sn34_he.h"
#include "profile.h"
#include "analog_matrix.h"

void sn34_matrix_scan_extra(matrix_row_t current_matrix[]) {
    static bool last, stable;
    static uint16_t since;
    bool pressed = !(SN_GPIO3->DATAIN & (1u << 10));
    if (pressed != last) {
        last = pressed;
        since = timer_read();
    }
    if (timer_elapsed(since) >= BOOM68_BUTTON_DEBOUNCE_MS) stable = last;
    matrix_row_t mask = (matrix_row_t)1u << BOOM68_ENCODER_BUTTON_COL;
    if (stable) current_matrix[BOOM68_ENCODER_BUTTON_ROW] |= mask;
    else current_matrix[BOOM68_ENCODER_BUTTON_ROW] &= ~mask;
}

void housekeeping_task_kb(void) {
    sn34_he_task();
}

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
#if SN34_PROFILE_HOTKEYS_ENABLE
    static matrix_row_t consumed[MATRIX_ROWS];
    extern matrix_row_t virtual_matrix[MATRIX_ROWS];
    uint8_t row = record->event.key.row, col = record->event.key.col;
    bool consumed_release = false;
    if (row < MATRIX_ROWS && col < MATRIX_COLS) {
        matrix_row_t bit = (matrix_row_t)1u << col;
        // Clear our press/release bookkeeping even if the user vetoes release.
        if (!record->event.pressed && (consumed[row] & bit)) {
            consumed[row] &= ~bit;
            consumed_release = true;
        }
    }
#endif
    bool allowed = process_record_user(keycode, record);
#if SN34_PROFILE_HOTKEYS_ENABLE
    if (consumed_release) return false;
#endif
    if (!allowed || !process_record_profile(keycode, record)) return false;
#if SN34_PROFILE_HOTKEYS_ENABLE
    if (row < MATRIX_ROWS && col < MATRIX_COLS) {
        matrix_row_t bit = (matrix_row_t)1u << col;
        bool profile_key = (row == PROF_TRIG_KEY_ROW && col == PROF_TRIG_KEY_COL) ||
                           (row == PROF_1_KEY_ROW && col == PROF_1_KEY_COL) ||
                           (row == PROF_2_KEY_ROW && col == PROF_2_KEY_COL) ||
                           (row == PROF_3_KEY_ROW && col == PROF_3_KEY_COL);
        if (record->event.pressed && profile_key && (layer_state & SN34_FN_LAYER_MASK) &&
            (virtual_matrix[PROF_TRIG_KEY_ROW] & ((matrix_row_t)1u << PROF_TRIG_KEY_COL))) {
            // The shared profile task reads the physical chord. Suppress P and
            // the Fn-layer mute/play/stop actions while that chord is held.
            consumed[row] |= bit;
            return false;
        }
    }
#endif
    return true;
}

#ifdef RGB_MATRIX_ENABLE
bool rgb_matrix_indicators_kb(void) {
    if (!rgb_matrix_indicators_user()) return false;
    analog_matrix_indicator();
    if (analog_matrix_calibrating()) return true;

    // Physical left-to-right order, following the light-box coordinates.
    static const uint8_t profile_leds[] = {93, 92};
    static const uint8_t layer_leds[] = {69, 68, 67};
    uint8_t value = rgb_matrix_get_val();
    uint8_t profile = profile_get_current_index();
    uint8_t layer = get_highest_layer(layer_state | default_layer_state);
    for (uint8_t i = 0; i < ARRAY_SIZE(profile_leds); ++i) {
        if (profile == i + 1) rgb_matrix_set_color(profile_leds[i], value, value, value);
    }
    if (layer >= 1 && layer <= ARRAY_SIZE(layer_leds)) rgb_matrix_set_color(layer_leds[layer - 1], value, value, value);
    if (host_keyboard_led_state().caps_lock) {
        rgb_matrix_set_color(g_led_config.matrix_co[3][0], value, value, value);
    }
    return true;
}
#endif
