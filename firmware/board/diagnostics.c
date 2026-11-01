// SPDX-License-Identifier: GPL-2.0-or-later
#include "diagnostics.h"
#include "hardware_registers.generated.h"

unsigned bat68_snapshot_words(void){return sizeof(snapshot_addresses)/sizeof(snapshot_addresses[0]);}
bool bat68_snapshot_word(unsigned index,uint32_t *value){
    if(index>=bat68_snapshot_words())return false;
    *value=*(volatile const uint32_t*)(uintptr_t)snapshot_addresses[index];
    return true;
}
