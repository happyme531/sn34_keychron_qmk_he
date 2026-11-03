// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic board used only for compile/emulation coverage of shared drivers.
#include "quantum.h"
#include "sn34_he.h"
#include "profile.h"
#include "analog_matrix.h"
void housekeeping_task_kb(void) {
    sn34_he_task();
}
bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    return process_record_user(keycode, record) && process_record_profile(keycode, record);
}
#ifdef RGB_MATRIX_ENABLE
bool rgb_matrix_indicators_kb(void) {
    if (!rgb_matrix_indicators_user()) return false;
    analog_matrix_indicator();
    return true;
}
#endif
