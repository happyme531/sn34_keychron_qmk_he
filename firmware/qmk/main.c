// SPDX-License-Identifier: GPL-2.0-or-later
#include "sn34f28x_hal.h"
#include "native.h"
#include "mailbox.h"
#include "platform.h"
#include "sn34_flash.h"
#include "rgb_matrix.h"
#include "perf.h"
#include "profile.h"
extern uint8_t __data_load[],__data_start[],__data_end[],__bss_start[],__bss_end[],native_vectors[];
static IWDG_Handle_T watchdog;
volatile uint32_t native_usb_loops;
volatile uint8_t native_restart_requested,native_boot_requested;
static void boot(void){
    __disable_irq();
    if(sn34_flash_invalidate_application())NVIC_SystemReset();
    __DSB();__ISB();__HAL_RCC_SET_REMAP_BOOT_CODE();__HAL_RCC_REBOOT();
    for(;;)__NOP();
}
void HAL_IWDG_MspInit(IWDG_Handle_T *h){(void)h;__HAL_RCC_WDT_CLK_ENABLE();__HAL_RCC_WDT_RESET();}
void native_reset(void){
    __disable_irq();SysTick->CTRL=0;
    SCB->CPACR|=0xfu<<20;__DSB();__ISB();
    for(unsigned i=0;i<3;i++){NVIC->ICER[i]=~0u;NVIC->ICPR[i]=~0u;}
    SCB->VTOR=(uint32_t)native_vectors;
    for(uint8_t *p=__data_start,*s=__data_load;p<__data_end;)*p++=*s++;
    for(uint8_t *p=__bss_start;p<__bss_end;)*p++=0;
    __DSB();__ISB(); // Publish initialized state before starting peripherals.
    for(unsigned i=0;i<16;i++)NATIVE_MAILBOX[i]=0;
    extern int main(void);main();NVIC_SystemReset();
}
void platform_setup(void){
    native_time_init();
    watchdog.instance=SN_WDT;watchdog.init.mode=IWDG_MODE_RESET;watchdog.init.timer_constant=32000u*20u;
    if(HAL_IWDG_Init(&watchdog)!=HAL_OK)boot();
    __enable_irq();int result=native_clock_init();
    NATIVE_MAILBOX[2]=result;NATIVE_MAILBOX[3]=HAL_RCC_GetHCLKFreq();
    if(result)boot();native_board_init();
    if(native_scan_init())boot();
    // Return to upstream quantum/main.c with ADC IRQs active. QMK owns its
    // keyboard setup, protocol initialization, tasks and housekeeping order.
}
void protocol_post_task(void){
    uint32_t started=bat68_cpu_clock();
    // Complete the blackout after an in-flight SPI frame finishes, even while
    // keyboard_task is gated during USB suspend.
    if(bat68_usb_suspended())rgb_matrix_task();
    // Layer actions have now run, including remapped Tri Layer / Layer-Tap
    // Fn keys. Keep Keychron's Fn+P+Z/X/C task in the normal QMK lifecycle.
    if(bat68_host_ready())process_profile_select_combo();
    bat68_host_task();bat68_indicators_task();bat68_eeprom_task();
    native_usb_loops++;HAL_IWDG_Refresh(&watchdog);
    bat68_post_cycles+=bat68_cpu_clock()-started;
    if(native_boot_requested){HAL_Delay(50);boot();}
    if(native_restart_requested && !native_usb_reply_queued()){HAL_Delay(100);NVIC_SystemReset();}
}
void native_fault(uint32_t *stack,uint32_t link,uint32_t exception){
    NATIVE_MAILBOX[7]=exception;NATIVE_MAILBOX[9]=link;
    if((uintptr_t)stack>=BAT68_RAM_ORIGIN&&(uintptr_t)stack<=BAT68_RAM_ORIGIN+BAT68_RAM_SIZE-32u)NATIVE_MAILBOX[8]=stack[6];
    NVIC_SystemReset();
}
