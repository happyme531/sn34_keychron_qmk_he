// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
unsigned bat68_snapshot_words(void);
bool bat68_snapshot_word(unsigned index,uint32_t *value);
