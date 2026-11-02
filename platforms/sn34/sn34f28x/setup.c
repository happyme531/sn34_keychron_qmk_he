// SPDX-License-Identifier: GPL-2.0-or-later
#include "sn34f28x_hal.h"
#include "native.h"
#include "sn34_bootloader.h"
extern uint8_t __data_load[],__data_start[],__data_end[],__bss_start[],__bss_end[],native_vectors[];
static IWDG_Handle_T watchdog;
volatile uint8_t native_restart_requested,native_boot_requested;

void HAL_IWDG_MspInit(IWDG_Handle_T *h){(void)h;__HAL_RCC_WDT_CLK_ENABLE();__HAL_RCC_WDT_RESET();}
void native_reset(void){
    __disable_irq();SysTick->CTRL=0;
    SCB->CPACR|=0xfu<<20;__DSB();__ISB();
    for(unsigned i=0;i<3;i++){NVIC->ICER[i]=~0u;NVIC->ICPR[i]=~0u;}
    SCB->VTOR=(uint32_t)native_vectors;
    for(uint8_t *p=__data_start,*s=__data_load;p<__data_end;)*p++=*s++;
    for(uint8_t *p=__bss_start;p<__bss_end;)*p++=0;
    __DSB();__ISB(); // Publish initialized state before starting peripherals.
    extern int main(void);main();NVIC_SystemReset();
}
void platform_setup(void){
    native_time_init();
    watchdog.instance=SN_WDT;watchdog.init.mode=IWDG_MODE_RESET;watchdog.init.timer_constant=32000u*20u;
    if(HAL_IWDG_Init(&watchdog)!=HAL_OK)sn34_bootloader_enter();
    __enable_irq();int result=native_clock_init();
    if(result)sn34_bootloader_enter();
    native_board_init();
    // QMK's matrix_setup starts the selected scanner after platform setup.
}
void native_reset_task(void) {
    HAL_IWDG_Refresh(&watchdog);
    if (native_boot_requested) { HAL_Delay(50); sn34_bootloader_enter(); }
    if (native_restart_requested) { HAL_Delay(100); NVIC_SystemReset(); }
}
void native_fault(void) { NVIC_SystemReset(); }
