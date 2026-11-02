// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic board used only for compile/emulation coverage of shared drivers.
#include "quantum.h"
#include "sn34.h"
#include "sn34_eeprom.h"
#include "sn34_he.h"
#include "profile.h"
#include "analog_matrix.h"
void housekeeping_task_kb(void) {
    if (sn34_host_ready()) process_profile_select_combo();
    sn34_eeprom_task(sn34_he_idle());
}
#ifdef RGB_MATRIX_ENABLE
bool rgb_matrix_indicators_kb(void) {
    analog_matrix_indicator();
    return rgb_matrix_indicators_user();
}
#endif
