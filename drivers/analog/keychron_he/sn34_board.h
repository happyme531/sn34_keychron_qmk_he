// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include "board_config.h"
typedef struct { uint16_t raw_slot, matrix_slot, idle, bottom; } board_key_t;
extern const board_key_t board_keys[SN34_KEY_COUNT];
