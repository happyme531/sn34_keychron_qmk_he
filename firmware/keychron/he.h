// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "matrix.h"
#include "bat68_eeprom.h"
void bat68_he_init(void);
void bat68_he_scan(const uint16_t raw[96], matrix_row_t next[MATRIX_ROWS]);
int bat68_he_command(const uint8_t *rx, uint8_t *tx, bool released);
