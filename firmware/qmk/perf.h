// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "sn34f28x_hal.h"
#include "native.h"
// Exclusive main-context cycles: remove ADC and USB interrupt bodies. These
// counters describe task cost, not CPU utilization of a busy-polling loop.
static inline uint32_t bat68_cpu_clock(void){
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t value=DWT->CYCCNT-native_adc_cycles-native_usb_irq_cycles;
    __set_PRIMASK(saved);return value;
}
extern uint32_t bat68_pre_cycles,bat68_key_cycles,bat68_post_cycles;
extern uint32_t bat68_he_cycles,bat68_he_max_cycles,bat68_key_max_cycles;
