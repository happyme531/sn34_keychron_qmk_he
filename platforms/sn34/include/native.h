// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include <stdbool.h>
void native_time_init(void);
int native_clock_init(void);
void native_board_init(void);
extern volatile uint8_t native_restart_requested;
extern volatile uint8_t native_boot_requested;
void native_reset(void) __attribute__((noreturn));
void native_reset_task(void);
