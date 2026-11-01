// SPDX-License-Identifier: GPL-2.0-or-later
#include "diagnostics.h"
#include "hardware_registers.generated.h"

unsigned sn34_snapshot_words(void){return sizeof(snapshot_addresses)/sizeof(snapshot_addresses[0]);}
bool sn34_snapshot_word(unsigned index,uint32_t *value){
    if(index>=sn34_snapshot_words())return false;
    *value=*(volatile const uint32_t*)(uintptr_t)snapshot_addresses[index];
    return true;
}
