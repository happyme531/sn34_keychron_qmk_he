// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "sn34f28x_hal.h"
#include "native.h"
// Exclusive main-context cycles: remove ADC and USB interrupt bodies. These
// counters describe task cost, not CPU utilization of a busy-polling loop.
static inline uint32_t sn34_cpu_clock(void){
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t value=DWT->CYCCNT-native_adc_cycles-native_usb_irq_cycles;
    __set_PRIMASK(saved);return value;
}
extern uint32_t sn34_pre_cycles,sn34_key_cycles,sn34_post_cycles;
extern uint32_t sn34_he_cycles,sn34_he_max_cycles,sn34_key_max_cycles;
