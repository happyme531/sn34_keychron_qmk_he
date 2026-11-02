// SPDX-License-Identifier: GPL-2.0-or-later
// Chip Flash operations using the unmodified SONiX SDK v2.1.4 Flash HAL.
#include <stdint.h>
#include "sn34f28x_hal_flash.h"
#include "sn34_flash.h"
#include "board_config.h"
_Static_assert(SN34_PAGE_SIZE==512u,"SN34F28x Flash backend requires the chip's 512-byte page size");

extern FLASH_ProcessTypeDef pFlash;
extern HAL_Status_T FLASH_WaitForLastOperation(uint32_t timeout);

int sn34_flash_prepare(void){
    // HAL_FLASHEx_Erase does not short-circuit its initial wait failure.
    // Reject a stuck or failing controller before entering the erase API.
    if(FLASH_WaitForLastOperation(1000u)!=HAL_OK)return -2;
    HAL_InitFlash(); // determines the Boot/User offset and enables AUTO_HOLD
    if(pFlash.MapAddress!=SN34_BOOT_USER_OFFSET)return -1; // never operate in Boot mapping
    return 0;
}
int sn34_flash_program_user_page(uint32_t user_offset,const void *data){
    if(!data || user_offset%SN34_PAGE_SIZE || user_offset>SN34_APP_SIZE-SN34_PAGE_SIZE)return -1;
    int result=sn34_flash_prepare();if(result)return result;
    FLASH_EraseInitTypeDef erase={.TypeErase=FLASH_TYPEERASE_PAGES,
                                  .Page=user_offset/SN34_PAGE_SIZE,.NbPages=1};
    uint32_t failed_page=0xffffffffu;
    if(HAL_FLASHEx_Erase(&erase,&failed_page)!=HAL_OK)return -2;
    if(HAL_FLASH_Program_Page(user_offset,(uint8_t*)data)!=HAL_OK)return -3;
    __DSB();__ISB();
    return 0;
}
