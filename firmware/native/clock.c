// SPDX-License-Identifier: GPL-2.0-or-later
// Board clock/power setup using the public SONiX SDK source drivers.
#include "sn34f28x_hal.h"
#include "native.h"
#include "mailbox.h"

uint32_t SystemCoreClock;
void SCU_IRQHandler(void){HAL_SCU_IRQHandler();}
int native_clock_init(void){
    __HAL_RCC_ALWAYSON_CLK_ENABLE();HAL_InitFlash();
    // The trial may arrive with PLL already selected. Switch through IHRC so
    // oscillator/PLL configuration never depends on the previous application.
    SN_SCU->IHRCCTRL_b.IHRCEN=1;
    uint32_t start=HAL_GetTick();
    while(!SN_SCU->IHRCCTRL_b.IHRCRDY){if(HAL_GetTick()-start>100)return -1;}
    RCC_ClkConfig_t clocks={.ClockType=RCC_CLK_TYPE_SYSCLK|RCC_CLK_TYPE_HCLK|RCC_CLK_TYPE_APB0CLK|RCC_CLK_TYPE_APB1CLK,
        .SYSCLKSource=RCC_SYSCLK_SRC_IHRC,.AHBCLKDivider=RCC_SYSCLK_DIV1,
        .APB0CLKDivider=RCC_HCLK_DIV2,.APB1CLKDivider=RCC_HCLK_DIV2};
    NATIVE_MAILBOX[11]=0x10;
    if(HAL_RCC_ClockConfig(&clocks)!=HAL_OK)return -2;
    NATIVE_MAILBOX[11]=0x11;
    RCC_OscConfig_t oscillators={.OscillatorType=RCC_OSC_TYPE_IHRC|RCC_OSC_TYPE_EHS,
        .IHRCEn=RCC_OSCCLK_CFG_ON,.EHSEn=RCC_OSCCLK_CFG_ON,
        .PLL={.PLLEn=RCC_OSCCLK_CFG_ON,.PLLSource=RCC_PLL_SRC_EHS,.NS=64,.FS=RCC_PLL_DIV4}};
    if(HAL_RCC_OscConfig(&oscillators)!=HAL_OK)return -3;
    NATIVE_MAILBOX[11]=0x12;
    clocks.SYSCLKSource=RCC_SYSCLK_SRC_PLL;
    if(HAL_RCC_ClockConfig(&clocks)!=HAL_OK)return -4;
    NATIVE_MAILBOX[11]=0x13;
    NVIC_DisableIRQ(SCU_IRQn);NVIC_ClearPendingIRQ(SCU_IRQn);
    return HAL_RCC_GetHCLKFreq()==192000000u?0:-5;
}
void native_board_init(void){
    __HAL_RCC_GPIO_P0_CLK_ENABLE();__HAL_RCC_GPIO_P1_CLK_ENABLE();
    __HAL_RCC_GPIO_P2_CLK_ENABLE();__HAL_RCC_GPIO_P3_CLK_ENABLE();
    // GPIO output, direction and pull-up configuration captured on this board.
    // ADC mux/gate pins are then owned by scan.c. Crystal AFIO on P3 is kept
    // under HAL_RCC_OscConfig control.
    static const uint32_t output[]={2,0x10,0x200,0x100};
    static const uint32_t direction[]={0x4003,0xded0,0x1f8301,0x100};
    static const uint32_t pull[]={0x1ffffb,0x1fffdf,0x1f8301,0x1ffdff};
    SN_GPIO_Type ports[]={SN_GPIO0,SN_GPIO1,SN_GPIO2,SN_GPIO3};
    for(unsigned i=0;i<4;i++){
        ports[i]->DATAOUT=output[i];ports[i]->PUTYPE=0x1fffff;
        ports[i]->PULLEN=pull[i];ports[i]->DIR=direction[i];
    }
    SN_ALWAYSON->P0_AFIO0=0;SN_ALWAYSON->P0_AFIO1=0;
    SN_ALWAYSON->P0_AFIO2=0;SN_ALWAYSON->P0_AFIO3=0;
    SN_ALWAYSON->P1_AFIO0=0;SN_ALWAYSON->P1_AFIO1=0;SN_ALWAYSON->P1_AFIO2=0x10040;
}
