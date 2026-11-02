// SPDX-License-Identifier: GPL-2.0-or-later
// QMK custom bootloader: retained SONiX footer-validity Boot scheme.
#include "sn34f28x_hal.h"
#include "sn34_flash.h"
#include "sn34_bootloader.h"
#include "board_config.h"
int sn34_flash_invalidate_application(void){
    int result=sn34_flash_prepare();if(result)return result;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,
                                  .Page=SN34_FOOTER_PAGE/SN34_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    __DSB();__ISB();
    return *(volatile const uint32_t*)SN34_FOOTER_ADDRESS!=SN34_FOOTER_MAGIC?0:-3;
}
void sn34_bootloader_enter(void){
    __disable_irq();
    if(sn34_flash_invalidate_application())NVIC_SystemReset();
    __DSB();__ISB();__HAL_RCC_SET_REMAP_BOOT_CODE();__HAL_RCC_REBOOT();
    for(;;)__NOP();
}
