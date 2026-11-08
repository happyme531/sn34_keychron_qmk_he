// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// 67 Hall switches plus one independent digital encoder button.
// Logical matrix row 0 contains Fn only, so simultaneous Fn chords dispatch first.
#define SN34_KEY_COUNT 67
#define SN34_SAMPLE_COUNT 80
#define SN34_MUX_PHASES 5
#define SN34_EEPROM_BANK_SIZE 0x2000
#define SN34_EEPROM_BASE 0x25
#define SN34_EEPROM_MAGIC 0x42363857
#define SN34_EEPROM_VERSION 5
#define SN34_EEPROM_BANK0 0x79000
#define SN34_EEPROM_BANK1 0x7b000
#define SN34_VIA_EEPROM_DATE "2026-11-04-00:00:00"
// Reserve the same layout even in builds with RGB disabled.
#define SN34_CUSTOM_RGB_STORAGE_SIZE 512
#define BOOM68_ENCODER_BUTTON_ROW 4
#define BOOM68_ENCODER_BUTTON_COL 13
// Confirm detents and direction on hardware. OEM 11 -> 10 means volume up.
#ifndef BOOM68_ENCODER_RESOLUTION
#    define BOOM68_ENCODER_RESOLUTION 4
#endif
#ifndef BOOM68_ENCODER_REVERSE
#    define BOOM68_ENCODER_REVERSE 0
#endif
#define BOOM68_BUTTON_DEBOUNCE_MS 5
// Let the selected sensor bank settle before the first ADC conversion.
#define BOOM68_BANK_SETTLE_US 8
#include "sn34_defaults.h"
