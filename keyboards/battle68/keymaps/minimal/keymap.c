// SPDX-License-Identifier: GPL-2.0-or-later
// Minimal keymap and hook fixture: no inclusion of the default keymap.
#include "quantum.h"
#include "profile.h"
#include "keychron_common.h"

const uint16_t PROGMEM keymaps[4][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = {[0][0] = MO(1), [1][7] = KC_LGUI, [3][1] = QK_KB_30, [3][2] = QK_KB_31, [3][3] = PROF2},
    [1] = {[0][0] = KC_TRNS},
    [2] = {[0][0] = MO(3), [1][7] = KC_LGUI, [3][1] = QK_KB_30, [3][2] = QK_KB_31, [3][3] = PROF2},
    [3] = {[0][0] = KC_TRNS},
};
uint32_t bat68_test_user_events, bat68_test_matrix_scans, bat68_test_matrix_inits;
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    (void)keycode; (void)record;
    bat68_test_user_events++;
    return true;
}
void matrix_init_user(void) { bat68_test_matrix_inits++; }
void matrix_scan_user(void) { bat68_test_matrix_scans++; }
