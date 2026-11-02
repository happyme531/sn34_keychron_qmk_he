// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stddef.h>
void sn34_he_calibration_init(void);
// A board can supply a validated factory-calibration record, e.g. over I2C.
// false selects its board-specific fallback endpoints.
bool sn34_board_calibration_read(void *buffer,size_t size);
