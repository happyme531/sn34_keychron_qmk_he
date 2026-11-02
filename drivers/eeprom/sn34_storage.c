// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34_eeprom.h"
static uint32_t due;
static bool requested;
static uint32_t revision;
static uint32_t last_key_activity;
void sn34_eeprom_task(bool idle){
    uint32_t now=timer_read32();
    if(!sn34_eeprom_dirty()){requested=false;last_key_activity=now;return;}
    // Persistence does not change active thresholds. Require no actuated
    // physical or logical key; sub-actuation Hall drift must not starve it.
    if(!idle)last_key_activity=now;
    if(revision!=sn34_eeprom_revision){revision=sn34_eeprom_revision;requested=true;due=timer_read32()+1500;}
    if(!requested){requested=true;due=timer_read32()+1500;return;}
    if((int32_t)(now-due)<0 || !idle || (uint32_t)(now-last_key_activity)<5000u)return;
    int result=sn34_eeprom_save_step();
    if(result>0 || !sn34_eeprom_dirty())requested=false;
    else if(result<0)due=timer_read32()+5000;
    else due=timer_read32()+5; // Let ADC publish complete frames between writes.
}
