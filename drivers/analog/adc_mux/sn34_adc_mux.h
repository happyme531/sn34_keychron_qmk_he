// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "board_config.h"
int native_scan_init(void);
extern volatile uint16_t native_raw[SN34_SAMPLE_COUNT];
extern volatile uint32_t native_scan_frames;
extern volatile uint8_t native_scan_phase;
bool native_scan_acquire(const uint16_t **raw,uint32_t *frame);
void native_scan_release(void);
