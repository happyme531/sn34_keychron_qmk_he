// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "board_config.generated.h"
void native_time_init(void);
int native_clock_init(void);
void native_board_init(void);
int native_usb_init(void);
void native_usb_task(void);
extern uint8_t native_keyboard_leds;
extern volatile uint8_t native_restart_requested;
extern volatile uint8_t native_boot_requested;
int native_usb_reply_queued(void);
void native_reset(void) __attribute__((noreturn));
extern volatile uint32_t native_usb_loops;
#if SN34_ENABLE_SCAN
int native_scan_init(void);
void native_set_mux_phase(unsigned phase);
extern volatile uint16_t native_raw[SN34_SAMPLE_COUNT];
extern volatile uint32_t native_scan_frames;
extern volatile uint8_t native_scan_phase;
bool native_scan_snapshot(uint16_t raw[SN34_SAMPLE_COUNT],uint32_t *frame);
bool native_scan_acquire(const uint16_t **raw,uint32_t *frame);
void native_scan_release(void);
extern volatile uint32_t native_adc_cycles,native_adc_calls,native_adc_max_cycles;
extern volatile uint32_t native_usb_irq_cycles;
extern volatile uint8_t native_scan_mode;
int native_scan_configure(unsigned mode);
#endif
