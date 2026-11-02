// SPDX-License-Identifier: GPL-2.0-or-later
// Board clock/power setup using the public SONiX SDK source drivers.
#include "sn34f28x_hal.h"
#include "native.h"
#include "board_config.h"
#include "wiring.h"

uint32_t SystemCoreClock;
void SCU_IRQHandler(void){HAL_SCU_IRQHandler();}
int native_clock_init(void){
    __HAL_RCC_ALWAYSON_CLK_ENABLE();HAL_InitFlash();
    // The MCU may arrive with PLL already selected. Switch through IHRC so
    // oscillator/PLL configuration never depends on the previous application.
    SN_SCU->IHRCCTRL_b.IHRCEN=1;
    uint32_t start=HAL_GetTick();
    while(!SN_SCU->IHRCCTRL_b.IHRCRDY){if(HAL_GetTick()-start>100)return -1;}
    RCC_ClkConfig_t clocks={.ClockType=RCC_CLK_TYPE_SYSCLK|RCC_CLK_TYPE_HCLK|RCC_CLK_TYPE_APB0CLK|RCC_CLK_TYPE_APB1CLK,
        .SYSCLKSource=RCC_SYSCLK_SRC_IHRC,.AHBCLKDivider=RCC_SYSCLK_DIV1,
        .APB0CLKDivider=RCC_HCLK_DIV2,.APB1CLKDivider=RCC_HCLK_DIV2};
    if(HAL_RCC_ClockConfig(&clocks)!=HAL_OK)return -2;
    RCC_OscConfig_t oscillators={.OscillatorType=RCC_OSC_TYPE_IHRC|RCC_OSC_TYPE_EHS,
        .IHRCEn=RCC_OSCCLK_CFG_ON,.EHSEn=RCC_OSCCLK_CFG_ON,
        .PLL={.PLLEn=RCC_OSCCLK_CFG_ON,.PLLSource=RCC_PLL_SRC_EHS,.NS=SN34_PLL_NS,.FS=SN34_PLL_FS}};
    if(HAL_RCC_OscConfig(&oscillators)!=HAL_OK)return -3;
    clocks.SYSCLKSource=RCC_SYSCLK_SRC_PLL;
    if(HAL_RCC_ClockConfig(&clocks)!=HAL_OK)return -4;
    NVIC_DisableIRQ(SCU_IRQn);NVIC_ClearPendingIRQ(SCU_IRQn);
    return HAL_RCC_GetHCLKFreq()==SN34_CLOCK_HZ?0:-5;
}
void native_board_init(void){sn34_board_gpio_init();}
