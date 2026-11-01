// SPDX-License-Identifier: GPL-2.0-or-later
// Board policy around the unmodified SONiX SDK v2.1.4 Flash HAL.
#include <stdint.h>
#include "sn34f28x_hal_flash.h"
#include "sn34_flash.h"
#if BAT68_QMK_PLATFORM
#include "bat68_storage.generated.h"
#else
#define BAT68_PAGE_SIZE 512u
#define BAT68_BOOT_USER_OFFSET 0x2000u
#define BAT68_LEGACY_KEYMAP_PAGE0 0x7d000u
#define BAT68_LEGACY_KEYMAP_PAGE1 0x7d200u
#define BAT68_FOOTER_PAGE 0x7de00u
#define BAT68_FOOTER_ADDRESS 0x7dffcu
#define BAT68_FOOTER_MAGIC 0xaaaa5555u
#endif

extern FLASH_ProcessTypeDef pFlash;
extern HAL_Status_T FLASH_WaitForLastOperation(uint32_t timeout);
#ifndef BAT68_NATIVE_TIMEBASE
static uint32_t tick_last,tick_remainder,tick_ms,cycles_per_ms;

// The SDK's polling timeout must advance while the keymap save masks IRQs.
// DWT provides a CPU clock counter independent of the SysTick interrupt.
uint32_t HAL_GetTick(void){
    uint32_t now=DWT->CYCCNT,delta=now-tick_last;
    tick_last=now;
    if(!cycles_per_ms)return 0;
    tick_ms+=delta/cycles_per_ms;
    tick_remainder+=delta%cycles_per_ms;
    if(tick_remainder>=cycles_per_ms){tick_remainder-=cycles_per_ms;tick_ms++;}
    return tick_ms;
}
#endif

static int prepare_flash(void){
#ifndef BAT68_NATIVE_TIMEBASE
    cycles_per_ms=HAL_RCC_GetHCLKFreq()/1000u;
    if(!cycles_per_ms)return -1;
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    tick_last=DWT->CYCCNT;tick_remainder=0;tick_ms=0;
#endif
    // HAL_FLASHEx_Erase does not short-circuit its initial wait failure.
    // Reject a stuck or failing controller before entering the erase API.
    if(FLASH_WaitForLastOperation(1000u)!=HAL_OK)return -2;
    HAL_InitFlash(); // determines the Boot/User offset and enables AUTO_HOLD
    if(pFlash.MapAddress!=BAT68_BOOT_USER_OFFSET)return -1; // never operate in Boot mapping
    return 0;
}
static int write_page(uint32_t user_offset,const void *data){
    int result=prepare_flash();if(result)return result;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,
                                  .Page=user_offset/BAT68_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    if(HAL_FLASH_Program_Page(user_offset,(uint8_t*)data)!=HAL_OK)return -3;
    __DSB();__ISB();
    return 0;
}
int sn34_flash_write_settings_page(uint32_t user_offset,const void *data){
    if((user_offset!=BAT68_LEGACY_KEYMAP_PAGE0&&user_offset!=BAT68_LEGACY_KEYMAP_PAGE1)||!data)return -1;
    return write_page(user_offset,data);
}
#if BAT68_KEYCHRON_HE
int sn34_flash_write_eeprom_page(uint32_t user_offset,const void *data){
#if BAT68_QMK_PLATFORM
    if(user_offset<BAT68_EEPROM_BANK0||user_offset>=BAT68_EEPROM_END||(user_offset&(BAT68_PAGE_SIZE-1u))||!data)return -1;
#else
    if(user_offset<0x7b000u||user_offset>=0x7d000u||(user_offset&511u)||!data)return -1;
#endif
    return write_page(user_offset,data);
}
#endif
int sn34_flash_invalidate_application(void){
    int result=prepare_flash();if(result)return result;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,
                                  .Page=BAT68_FOOTER_PAGE/BAT68_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    __DSB();__ISB();
    // The Bootloader tests the valid signature, not an assumed erase polarity.
    // Real silicon reads zero from this erased page on the current board.
    return *(volatile const uint32_t*)BAT68_FOOTER_ADDRESS!=BAT68_FOOTER_MAGIC?0:-3;
}
int sn34_flash_validate_application(void){
    if(*(volatile const uint32_t*)BAT68_FOOTER_ADDRESS==BAT68_FOOTER_MAGIC)return 0;
    int result=prepare_flash();if(result)return result;
    // The standalone image reserves this entire page: zero padding and the
    // single valid-footer word. No keyboard settings or executable code here.
    uint32_t page[BAT68_PAGE_SIZE/sizeof(uint32_t)]={0};page[BAT68_PAGE_SIZE/sizeof(uint32_t)-1]=BAT68_FOOTER_MAGIC;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,.Page=BAT68_FOOTER_PAGE/BAT68_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    if(HAL_FLASH_Program_Page(BAT68_FOOTER_PAGE,(uint8_t*)page)!=HAL_OK)return -3;
    __DSB();__ISB();
    const volatile uint32_t *written=(const volatile uint32_t*)BAT68_FOOTER_PAGE;
    for(unsigned i=0;i<BAT68_PAGE_SIZE/sizeof(uint32_t);i++)if(written[i]!=page[i])return -3;
    return 0;
}
