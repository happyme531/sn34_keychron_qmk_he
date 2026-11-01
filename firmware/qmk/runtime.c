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
void protocol_setup(void){bat68_eeprom_init();bat68_host_init();bat68_indicators_init();}
void protocol_pre_init(void){}
void protocol_post_init(void){if(native_usb_init())native_boot_requested=1;}
uint32_t bat68_main_loops,bat68_gated_loops,bat68_max_loop_gap_cycles;
uint32_t bat68_pre_cycles,bat68_key_cycles,bat68_post_cycles;
uint32_t bat68_he_cycles,bat68_he_max_cycles,bat68_key_max_cycles;
static uint32_t previous_loop;
void protocol_pre_task(void){
    uint32_t started=bat68_cpu_clock();
    uint32_t now=DWT->CYCCNT;
    if(bat68_main_loops && now-previous_loop>bat68_max_loop_gap_cycles)bat68_max_loop_gap_cycles=now-previous_loop;
    previous_loop=now;bat68_main_loops++;
    native_usb_task();bat68_host_task();
    bat68_pre_cycles+=bat68_cpu_clock()-started;
}
void protocol_keyboard_task(void){
    uint32_t started=bat68_cpu_clock();
    if(bat68_host_ready())keyboard_task();else bat68_gated_loops++;
    uint32_t elapsed=bat68_cpu_clock()-started;bat68_key_cycles+=elapsed;
    if(elapsed>bat68_key_max_cycles)bat68_key_max_cycles=elapsed;
}
