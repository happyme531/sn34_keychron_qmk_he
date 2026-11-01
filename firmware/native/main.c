// SPDX-License-Identifier: GPL-2.0-or-later
// Source-built application. Trial builds return to the installed bridge;
// standalone builds own the reset vector and run until reset or OTA request.
#include "sn34f28x_hal.h"
#include "native.h"
#include "mailbox.h"
#if BAT68_ENABLE_KEYBOARD
#include "sn34_flash.h"
#endif
extern uint8_t __data_load[],__data_start[],__data_end[],__bss_start[],__bss_end[],native_vectors[];
static IWDG_Handle_T trial_watchdog;
volatile uint32_t native_usb_loops;
volatile uint8_t native_restart_requested;
volatile uint8_t native_boot_requested;
static void enter_bootloader(void){
#if BAT68_ENABLE_KEYBOARD
    // The retained Bootloader enters USB ISP when its application-valid footer
    // is absent. A complete hardware reboot gives it clean peripheral state.
    // The existing OEM OTA restores the footer after programming User ROM.
    uint32_t saved=__get_PRIMASK();__disable_irq();
    int result=sn34_flash_invalidate_application();
    if(result){NATIVE_MAILBOX[2]=(uint32_t)result;native_boot_requested=0;__set_PRIMASK(saved);return;}
    __DSB();__ISB();
    __HAL_RCC_SET_REMAP_BOOT_CODE();__HAL_RCC_REBOOT();
    for(;;)__NOP();
#else
    native_boot_requested=0;
#endif
}
void HAL_IWDG_MspInit(IWDG_Handle_T *handle){
    (void)handle;__HAL_RCC_WDT_CLK_ENABLE();__HAL_RCC_WDT_RESET();
}
void native_reset(void){
    __disable_irq();SysTick->CTRL=0;
#if BAT68_KEYCHRON_HE
    SCB->CPACR |= (0xfu << 20); __DSB(); __ISB();
#endif
    for(unsigned i=0;i<3;i++){NVIC->ICER[i]=0xffffffff;NVIC->ICPR[i]=0xffffffff;}
    SCB->VTOR=(uint32_t)native_vectors;__DSB();__ISB();
    for(uint8_t *p=__data_start,*s=__data_load;p<__data_end;) *p++=*s++;
    for(uint8_t *p=__bss_start;p<__bss_end;) *p++=0;
    for(unsigned i=0;i<16;i++)NATIVE_MAILBOX[i]=0;
    NATIVE_MAILBOX[0]=0x4e383642;NATIVE_MAILBOX[1]=1;
    native_time_init();
    NATIVE_MAILBOX[3]=HAL_RCC_GetHCLKFreq();
    trial_watchdog.instance=SN_WDT;
    trial_watchdog.init.mode=IWDG_MODE_RESET;
    trial_watchdog.init.timer_constant=32000u*20u;
    if(HAL_IWDG_Init(&trial_watchdog)!=HAL_OK)NVIC_SystemReset();
    NATIVE_MAILBOX[1]=2;NATIVE_MAILBOX[13]=trial_watchdog.init.timer_constant;
#if BAT68_BRINGUP_GUARD
    // First standalone bring-up remains recoverable through USB: keep the
    // footer invalid until the host verifies this image and explicitly commits.
    // A crash/watchdog reset before commit returns to the retained Bootloader.
    if(sn34_flash_invalidate_application())NVIC_SystemReset();
#endif
#if BAT68_COLD_INIT
    // RCC's FCS transition waits for its dedicated SCU interrupt. Every other
    // source is still disabled by this startup's NVIC reset above.
    __enable_irq();
    int clock_result=native_clock_init();__disable_irq();
    NATIVE_MAILBOX[2]=(uint32_t)clock_result;
    if(clock_result){
#if BAT68_STANDALONE
        enter_bootloader();
#endif
        NVIC_SystemReset();
    }
    NATIVE_MAILBOX[3]=HAL_RCC_GetHCLKFreq();
    native_board_init();
#endif
    int result=native_usb_init();NATIVE_MAILBOX[2]=(uint32_t)result;NATIVE_MAILBOX[1]=3;
#if BAT68_ENABLE_SCAN
    if(result==0){NATIVE_MAILBOX[12]=1;result=native_scan_init();NATIVE_MAILBOX[12]=(uint32_t)result;}
#endif
#if BAT68_ENABLE_KEYBOARD
    if(result==0)native_keyboard_init();
#endif
    __enable_irq();
    uint32_t start=HAL_GetTick();
    while(result==0&&(BAT68_STANDALONE||HAL_GetTick()-start<BAT68_TRIAL_MILLISECONDS)){
        native_usb_task();native_usb_loops++;
#if BAT68_ENABLE_KEYBOARD
        native_keyboard_task();
        HAL_IWDG_Refresh(&trial_watchdog);
#endif
        if(native_restart_requested&&!native_usb_reply_queued()){HAL_Delay(100);break;}
        if(native_boot_requested){HAL_Delay(50);enter_bootloader();}
        NATIVE_MAILBOX[5]=native_usb_loops;NATIVE_MAILBOX[6]=HAL_GetTick();
    }
    NATIVE_MAILBOX[15]=0x444f4e45;
#if BAT68_STANDALONE
    if(result)enter_bootloader();
#endif
    NVIC_SystemReset();
}
void native_fault(uint32_t *stack,uint32_t link,uint32_t exception){
    NATIVE_MAILBOX[7]=exception;NATIVE_MAILBOX[9]=link;
    if((uintptr_t)stack>=0x20000000u&&(uintptr_t)stack<=0x20027fe0u)NATIVE_MAILBOX[8]=stack[6];
    NATIVE_MAILBOX[1]=0xdead;
    NVIC_SystemReset();
}
