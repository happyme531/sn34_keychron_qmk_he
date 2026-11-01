// SPDX-License-Identifier: GPL-2.0-or-later
#include "sn34f28x_hal.h"
#include "native.h"
static uint32_t last_cycles,remainder,millis,cycles_per_ms;
void native_time_init(void){
    cycles_per_ms=HAL_RCC_GetHCLKFreq()/1000u;
    if(!cycles_per_ms)cycles_per_ms=12000;
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    last_cycles=DWT->CYCCNT;remainder=0;millis=0;
}
uint32_t HAL_GetTick(void){
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t now=DWT->CYCCNT,delta=now-last_cycles;last_cycles=now;
    if(cycles_per_ms){
        millis+=delta/cycles_per_ms;remainder+=delta%cycles_per_ms;
        if(remainder>=cycles_per_ms){remainder-=cycles_per_ms;millis++;}
    }
    uint32_t value=millis;__set_PRIMASK(saved);return value;
}
void HAL_Delay(uint32_t delay){uint32_t start=HAL_GetTick();while(HAL_GetTick()-start<delay){}}
HAL_Status_T HAL_InitTick(uint32_t priority){(void)priority;native_time_init();return HAL_OK;}
uint32_t HAL_GetTickPrio(void){return 0;}
