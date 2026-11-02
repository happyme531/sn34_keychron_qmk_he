// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "analog_matrix.h"
#include "profile.h"
#include "game_controller_common.h"
#include "sn34_he.h"
#include "sn34_adc_mux.h"
#include "sn34_board.h"
#include "hall_curve.h"
#include "hall_curve.inc"
// Invert the stock magnetic response after normalizing each key's measured
// released/bottom endpoints. This corrects shape without changing HE's 0..240
// range, profile thresholds or gamepad normalization.
uint8_t sn34_hall_convert(uint16_t value,uint16_t zero,uint16_t bottom){
    if(zero<=bottom || value>=zero)return 0;
    if(value<=bottom)return 240;
    uint32_t adc=((uint32_t)(zero-value)*65535u)/(zero-bottom);
    unsigned lo=0,hi=sizeof(sn34_hall_adc_curve)/sizeof(sn34_hall_adc_curve[0])-1;
    unsigned end=hi;
    while(hi-lo>1){unsigned mid=(lo+hi)/2;if(adc<sn34_hall_adc_curve[mid])hi=mid;else lo=mid;}
    uint32_t fraction=((adc-sn34_hall_adc_curve[lo])*256u)/(sn34_hall_adc_curve[hi]-sn34_hall_adc_curve[lo]);
    return ((lo*256u+fraction)*240u+end*128u)/(end*256u);
}
matrix_row_t analog_matrix_mask[MATRIX_ROWS];
matrix_row_t analog_raw_matrix[MATRIX_ROWS],changed_matrix[MATRIX_ROWS];
extern matrix_row_t raw_matrix[MATRIX_ROWS],matrix[MATRIX_ROWS];
matrix_row_t virtual_matrix[MATRIX_ROWS];
extern matrix_row_t okmc_matrix[MATRIX_ROWS],game_controller_matrix[MATRIX_ROWS];
uint8_t profile_gobal_mode[PROFILE_COUNT]={AKM_REGULAR,AKM_RAPID,AKM_REGULAR};
uint16_t default_profiles[PROFILE_COUNT][MATRIX_ROWS][MATRIX_COLS];
static uint32_t last_frame;
void sn34_he_init(void){
    for(unsigned i=0;i<SN34_KEY_COUNT;i++)
        analog_matrix_mask[board_keys[i].matrix_slot/MATRIX_COLS]|=1u<<(board_keys[i].matrix_slot%MATRIX_COLS);
    analog_matrix_init();
}
extern void sn34_analog_update_frame(const uint16_t samples[SN34_SAMPLE_COUNT]);
bool sn34_he_scan(void){
    const uint16_t *samples;
    if(!native_scan_acquire(&samples,&last_frame))return false;
    matrix_row_t before[MATRIX_ROWS];memcpy(before,analog_raw_matrix,sizeof(before));
    memset(analog_raw_matrix,0,sizeof(analog_raw_matrix));
    sn34_analog_update_frame(samples);
    native_scan_release();
    for(unsigned r=0;r<MATRIX_ROWS;r++)changed_matrix[r]=before[r]^analog_raw_matrix[r];
    analog_matrix_task();
    bool changed=false;
    for(unsigned r=0;r<MATRIX_ROWS;r++){
        matrix_row_t next=raw_matrix[r]&analog_matrix_mask[r];
        changed|=next!=matrix[r];raw_matrix[r]=next;
        // Keychron's virtual matrix represents advanced-mode activity for
        // matrix queries and indicators. DKS emits its own actions and must not also
        // dispatch the physical key's normal keycode through QMK.
        virtual_matrix[r]=next|okmc_matrix[r]|game_controller_matrix[r];
    }
    return changed;
}
bool sn34_physical_released(void){
    for(unsigned i=0;i<SN34_KEY_COUNT;i++){
        unsigned slot=board_keys[i].matrix_slot;
        if(analog_matrix_get_travel(slot/MATRIX_COLS,slot%MATRIX_COLS)>TRAVEL_SCALE)return false;
    }
    return true;
}
bool sn34_he_idle(void) {
    if (!sn34_matrix_released()) return false;
    for (unsigned row = 0; row < MATRIX_ROWS; row++) if (analog_raw_matrix[row]) return false;
    return true;
}
