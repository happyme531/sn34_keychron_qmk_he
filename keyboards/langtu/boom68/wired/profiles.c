// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "analog_matrix.h"
#include "profile.h"
uint8_t profile_gobal_mode[PROFILE_COUNT] = {AKM_REGULAR, AKM_RAPID, AKM_REGULAR};
const uint16_t PROGMEM default_profiles[PROFILE_COUNT][MATRIX_ROWS][MATRIX_COLS] = {0};
