// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34f28x_hal.h"
#include "sn34.h"
#include "sn34_eeprom.h"
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
    if (sn34_host_ready()) process_profile_select_combo();
    sn34_eeprom_task(sn34_he_idle());
}

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    if (!process_record_profile(keycode, record)) return false;
#if SN34_PROFILE_HOTKEYS_ENABLE
    static matrix_row_t consumed[MATRIX_ROWS];
    extern matrix_row_t virtual_matrix[MATRIX_ROWS];
    uint8_t row = record->event.key.row, col = record->event.key.col;
    if (row < MATRIX_ROWS && col < MATRIX_COLS) {
        matrix_row_t bit = (matrix_row_t)1u << col;
        // Consume the release too, including when Fn or P is released first.
        if (!record->event.pressed && (consumed[row] & bit)) {
            consumed[row] &= ~bit;
            return false;
        }
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
    return process_record_user(keycode, record);
}

#ifdef RGB_MATRIX_ENABLE
bool rgb_matrix_indicators_kb(void) {
    analog_matrix_indicator();
    return rgb_matrix_indicators_user();
}
#endif
