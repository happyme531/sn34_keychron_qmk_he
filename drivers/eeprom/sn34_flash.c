// SPDX-License-Identifier: GPL-2.0-or-later
#include "sn34_storage.generated.h"
#include "sn34_flash.h"
#include <stdbool.h>

int sn34_flash_write_eeprom_page(uint32_t user_offset,const void *data){
    bool first=user_offset>=SN34_EEPROM_BANK0 && user_offset<SN34_EEPROM_BANK0+SN34_EEPROM_BANK_SIZE;
    bool second=user_offset>=SN34_EEPROM_BANK1 && user_offset<SN34_EEPROM_BANK1+SN34_EEPROM_BANK_SIZE;
    if((!first && !second)||(user_offset&(SN34_PAGE_SIZE-1u))||!data)return -1;
    return sn34_flash_program_user_page(user_offset,data);
}
