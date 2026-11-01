// SPDX-License-Identifier: GPL-2.0-or-later
// Explicit backend for the retained SONiX footer-validity Boot scheme.
#include "sn34f28x_hal.h"
#include "sn34_flash.h"
#include "sn34_bootloader.h"
#include "sn34_storage.generated.h"
int sn34_flash_write_settings_page(uint32_t user_offset,const void *data){
    if((user_offset!=SN34_LEGACY_KEYMAP_PAGE0&&user_offset!=SN34_LEGACY_KEYMAP_PAGE1)||!data)return -1;
    return sn34_flash_program_user_page(user_offset,data);
}
int sn34_flash_invalidate_application(void){
    int result=sn34_flash_prepare();if(result)return result;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,
                                  .Page=SN34_FOOTER_PAGE/SN34_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    __DSB();__ISB();
    // The Bootloader tests the valid signature, not an assumed erase polarity.
    // Real silicon reads zero from this erased page on the current board.
    return *(volatile const uint32_t*)SN34_FOOTER_ADDRESS!=SN34_FOOTER_MAGIC?0:-3;
}
int sn34_flash_validate_application(void){
    if(*(volatile const uint32_t*)SN34_FOOTER_ADDRESS==SN34_FOOTER_MAGIC)return 0;
    int result=sn34_flash_prepare();if(result)return result;
    // The standalone image reserves this entire page: zero padding and the
    // single valid-footer word. No keyboard settings or executable code here.
    uint32_t page[SN34_PAGE_SIZE/sizeof(uint32_t)]={0};page[SN34_PAGE_SIZE/sizeof(uint32_t)-1]=SN34_FOOTER_MAGIC;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,.Page=SN34_FOOTER_PAGE/SN34_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    if(HAL_FLASH_Program_Page(SN34_FOOTER_PAGE,(uint8_t*)page)!=HAL_OK)return -3;
    __DSB();__ISB();
    const volatile uint32_t *written=(const volatile uint32_t*)SN34_FOOTER_PAGE;
    for(unsigned i=0;i<SN34_PAGE_SIZE/sizeof(uint32_t);i++)if(written[i]!=page[i])return -3;
    return 0;
}

void sn34_bootloader_enter(void){
    __disable_irq();
    if(sn34_flash_invalidate_application())NVIC_SystemReset();
    __DSB();__ISB();__HAL_RCC_SET_REMAP_BOOT_CODE();__HAL_RCC_REBOOT();
    for(;;)__NOP();
}
