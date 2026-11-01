// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#define MATRIX_ROWS 6
#define MATRIX_COLS 16
#define NO_PRINT
#define NO_DEBUG
#define NO_ACTION_ONESHOT
#define NO_ACTION_MACRO
#define NO_ACTION_FUNCTION
#define LAYER_STATE_8BIT
#define FAST_TIMER_T_SIZE 32
#define TAPPING_TERM 200
#define TAP_CODE_DELAY 0
#define IGNORE_ATOMIC_BLOCK
#define ANANLOG_MATRIX
#include "analog_matrix_eeconfig.h"
#define DEFAULT_ACTUATION_POINT 12
#define DEFAULT_RAPID_TRIGGER_SENSITIVITY 4
#define DEFAULT_ZERO_TRAVEL_VALUE 2300
#define DEFAULT_FULL_RANGE 700
// BAT68's magnets have no measured displacement curve yet. Use a linear
// normalized ADC fraction, not Keychron's polynomial for different switches.
#define REF_ZERO_TRAVEL 2300
#define REF_FULL_TRAVEL 1600
#define CONST_A1 0.0f
#define CONST_B1 -1.0f
#define CONST_C1 0.0f
#define CONST_D1 0.0f
#define EEPROM_CUSTOM
#define EEPROM_SIZE 3584
#define EECONFIG_BASE_ANALOG_MATRIX 37
#define EECONFIG_KB_DATA_SIZE EECONFIG_SIZE_ANALOG_MATRIX
#define VENDOR_ID 0x0c45
#define PROFILE_LED_MATRIX_LIST {0, 0, 0}
// Legacy diagnostics retain their original normalized 0..330 units.
#define BAT68_ACTUATION 100
#define BAT68_RELEASE 80
