// SPDX-License-Identifier: GPL-2.0-or-later
#include "sn34f28x_hal.h"

uint32_t timer_read32(void) { return HAL_GetTick(); }
uint16_t timer_read(void) { return (uint16_t)HAL_GetTick(); }
void timer_init(void) {}
void timer_clear(void) {}
void wait_ms(unsigned ms) { HAL_Delay(ms); }
void wait_us(unsigned us) {
    uint32_t per_us=HAL_RCC_GetHCLKFreq()/1000000u;
    while(us) {
        unsigned chunk=us>1000?1000:us; us-=chunk;
        uint32_t start=DWT->CYCCNT;
        while((uint32_t)(DWT->CYCCNT-start)<chunk*per_us) __NOP();
    }
}
