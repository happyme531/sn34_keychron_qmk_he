// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
unsigned sn34_snapshot_words(void);
bool sn34_snapshot_word(unsigned index,uint32_t *value);
