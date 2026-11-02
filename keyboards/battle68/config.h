// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "board/board_config.h"
#define SERIAL_NUMBER "B68QMK002"
#define SN34_WIN_BASE_LAYER 0
#define SN34_WIN_FN_LAYER 1
#define SN34_MAC_BASE_LAYER 2
#define SN34_MAC_FN_LAYER 3
#define SN34_FN_LAYER_MASK ((1u << SN34_WIN_FN_LAYER) | (1u << SN34_MAC_FN_LAYER))
#include "drivers/analog/keychron_he/config.h"
