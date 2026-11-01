// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "platform.h"
#include "native.h"
#include "perf.h"
#include "sn34f28x_hal.h"
#include "lib/lib8tion/lib8tion.h"
// DIGITAL_RAIN uses libc rand(); this freestanding platform uses QMK's
// existing lighting PRNG and returns the 31-bit range expected by newlib.
int rand(void){return (int)(((uint32_t)random16()<<15)|(random16()&0x7fff));}
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
int abs(int value) { return value<0?-value:value; }
void bootloader_jump(void) { native_boot_requested=1; }
void mcu_reset(void) { native_restart_requested=1; }
int8_t sendchar(uint8_t c) { (void)c; return 0; }
void protocol_setup(void){sn34_eeprom_init();sn34_host_init();sn34_indicators_init();}
void protocol_pre_init(void){}
void protocol_post_init(void){if(native_usb_init())native_boot_requested=1;}
uint32_t sn34_main_loops,sn34_gated_loops,sn34_max_loop_gap_cycles;
uint32_t sn34_pre_cycles,sn34_key_cycles,sn34_post_cycles;
uint32_t sn34_he_cycles,sn34_he_max_cycles,sn34_key_max_cycles;
static uint32_t previous_loop;
void protocol_pre_task(void){
    uint32_t started=sn34_cpu_clock();
    uint32_t now=DWT->CYCCNT;
    if(sn34_main_loops && now-previous_loop>sn34_max_loop_gap_cycles)sn34_max_loop_gap_cycles=now-previous_loop;
    previous_loop=now;sn34_main_loops++;
    native_usb_task();sn34_host_task();
    sn34_pre_cycles+=sn34_cpu_clock()-started;
}
void protocol_keyboard_task(void){
    uint32_t started=sn34_cpu_clock();
    if(sn34_host_ready())keyboard_task();else sn34_gated_loops++;
    uint32_t elapsed=sn34_cpu_clock()-started;sn34_key_cycles+=elapsed;
    if(elapsed>sn34_key_max_cycles)sn34_key_max_cycles=elapsed;
}
