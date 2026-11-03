// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "matrix.h"
void sn34_matrix_scan_extra(matrix_row_t current_matrix[]);
void sn34_he_calibration_init(void);
void sn34_he_task(void);
uint8_t sn34_hall_convert(uint16_t value, uint16_t zero, uint16_t bottom);
bool sn34_matrix_released(void);
bool sn34_physical_released(void);
bool sn34_he_idle(void);
