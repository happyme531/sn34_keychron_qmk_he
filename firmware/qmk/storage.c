// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "platform.h"
static uint32_t due;
static bool requested;
static uint32_t revision;
static uint32_t last_key_activity;
extern uint32_t bat68_eeprom_revision;
extern matrix_row_t analog_raw_matrix[MATRIX_ROWS];
bool bat68_storage_released(void){
    if(!bat68_matrix_released())return false;
    for(unsigned row=0;row<MATRIX_ROWS;row++)if(analog_raw_matrix[row])return false;
    return true;
}
void bat68_storage_diagnostics(uint8_t out[32]){
    memset(out,0,32);out[0]=1;out[1]=bat68_eeprom_dirty();
    out[2]=bat68_physical_released();out[3]=bat68_matrix_released();
    uint32_t values[]={timer_read32(),due,revision,bat68_eeprom_revision,last_key_activity,
        bat68_eeprom_sequence(),requested};memcpy(out+4,values,sizeof(values));
}
void bat68_eeprom_request_save(void){requested=true;due=timer_read32()+1000;}
void bat68_eeprom_task(void){
    uint32_t now=timer_read32();
    if(!bat68_eeprom_dirty()){requested=false;last_key_activity=now;return;}
    // Persistence does not change active thresholds. Require no actuated
    // physical or logical key; sub-actuation Hall drift must not starve it.
    bool released=bat68_storage_released();
    if(!released)last_key_activity=now;
    if(revision!=bat68_eeprom_revision){revision=bat68_eeprom_revision;requested=true;due=timer_read32()+1500;}
    if(!requested){requested=true;due=timer_read32()+1500;return;}
    if((int32_t)(now-due)<0 || !released || (uint32_t)(now-last_key_activity)<5000u)return;
    int result=bat68_eeprom_save_step();
    if(result>0 || !bat68_eeprom_dirty())requested=false;
    else if(result<0)due=timer_read32()+5000;
    else due=timer_read32()+5; // Let ADC publish complete frames between writes.
}
