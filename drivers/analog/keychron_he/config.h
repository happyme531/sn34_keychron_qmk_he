// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#ifndef __ASSEMBLER__
#include "platform_deps.h"
#endif
#include "board_config.h"
#define ANALOG_MATRIX_PLATFORM_HEADER "sn34_he.h"
#define ANALOG_MATRIX_TRAVEL_CONVERT sn34_hall_convert
#define ANALOG_MATRIX_FN_ACTIVE (SN34_PROFILE_HOTKEYS_ENABLE && (layer_state & SN34_FN_LAYER_MASK))
#define ANALOG_MATRIX_CALIBRATION_OFFSET (OFFSET_CURRENT_PROFILE + 1)
#include "analog_matrix_eeconfig.h"
#define AUTO_CALIB_RANGE_STRONG (DEFAULT_FULL_RANGE*9/10)
#define AUTO_CALIB_RANGE_MEDIUM (DEFAULT_FULL_RANGE*8/10)
#define AUTO_CALIB_RANGE_MINIMUM (DEFAULT_FULL_RANGE*7/10)
#define REF_ZERO_TRAVEL 2300
#define REF_FULL_TRAVEL 1600
#define CONST_A1 0.0f
#define CONST_B1 -1.0f
#define CONST_C1 0.0f
#define CONST_D1 0.0f
#define EEPROM_SIZE SN34_EEPROM_SIZE
#define EECONFIG_BASE_ANALOG_MATRIX SN34_EEPROM_BASE
#define EECONFIG_KB_DATA_SIZE EECONFIG_SIZE_ANALOG_MATRIX
#define KEYCHRON_NO_DFU_INFO
#define KEYCHRON_NO_LANGUAGE
#define KEYCHRON_NO_QUICK_START
#define RAW_EPSIZE 32
#define VIA_FIRMWARE_VERSION 5
#define VIA_EEPROM_COMPAT_DATE SN34_VIA_EEPROM_DATE

// The Launcher adapter uses VIA's Raw HID dispatcher. Other report features
// remain ordinary, optional QMK build settings.
#if !defined(RAW_ENABLE) || !defined(VIA_ENABLE)
#error "SN34 HE configuration requires Raw HID and VIA in rules.mk"
#endif
