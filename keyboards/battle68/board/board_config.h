// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Board wiring, calibration and persistence ABI. Keep the compatibility tests in sync.
#define SN34_KEY_COUNT 67
#define SN34_SAMPLE_COUNT 96
#define SN34_MUX_PHASES 8
#define SN34_EEPROM_BANK_SIZE 0x2000
#define SN34_EEPROM_BASE 0x25
#define SN34_EEPROM_MAGIC 0x45483842
#define SN34_EEPROM_COMMIT 0x4845434d
#define SN34_EEPROM_VERSION 3
#define SN34_EEPROM_LEGACY_VERSIONS ((1 << 1) | (1 << 2))
#define SN34_EEPROM_BANK0 0x79000
#define SN34_EEPROM_BANK1 0x7b000
#define SN34_VIA_EEPROM_DATE "2026-10-30-00:00:00"
#include "sn34_defaults.h"
