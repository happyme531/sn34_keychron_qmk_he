// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "ll_gpio_afio.h"
static inline void sn34_board_gpio_init(void){
__HAL_RCC_GPIO_P0_CLK_ENABLE();
SN_GPIO0->DATAOUT=2u;
SN_GPIO0->PUTYPE=0x1fffffu;
SN_GPIO0->PULLEN=2097147u;
SN_GPIO0->DIR=16387u;
__HAL_RCC_GPIO_P1_CLK_ENABLE();
SN_GPIO1->DATAOUT=16u;
SN_GPIO1->PUTYPE=0x1fffffu;
SN_GPIO1->PULLEN=2097119u;
SN_GPIO1->DIR=57040u;
__HAL_RCC_GPIO_P2_CLK_ENABLE();
SN_GPIO2->DATAOUT=512u;
SN_GPIO2->PUTYPE=0x1fffffu;
SN_GPIO2->PULLEN=2065153u;
SN_GPIO2->DIR=2065153u;
__HAL_RCC_GPIO_P3_CLK_ENABLE();
SN_GPIO3->DATAOUT=256u;
SN_GPIO3->PUTYPE=0x1fffffu;
SN_GPIO3->PULLEN=2096639u;
SN_GPIO3->DIR=256u;
SN_ALWAYSON->P0_AFIO0=0u;
SN_ALWAYSON->P0_AFIO1=0u;
SN_ALWAYSON->P0_AFIO2=0u;
SN_ALWAYSON->P0_AFIO3=0u;
SN_ALWAYSON->P1_AFIO0=0u;
SN_ALWAYSON->P1_AFIO1=0u;
SN_ALWAYSON->P1_AFIO2=65600u;
}
static inline void sn34_board_analog_pins(void){
SN_ALWAYSON->P2_AFIO0=415641984u;
SN_ALWAYSON->P2_AFIO1=415236492u;
SN_ALWAYSON->P2_AFIO2=12684u;
}
static inline void sn34_board_mux_phase(unsigned phase){
if(phase&(1u<<0)){SN_GPIO0->BSET=1u<<0;}else{SN_GPIO0->BCLR=1u<<0;}
}
static inline void sn34_board_scan_pins_init(void){
SN_GPIO0->DIR|=1u<<0;
SN_GPIO1->DIR|=1u<<12;
SN_GPIO2->PULLEN&=~31998u;SN_GPIO2->DIR&=~31998u;
}
static inline void sn34_board_sample_gate(void){SN_GPIO1->BCLR=1u<<12;}
static inline void sn34_board_scan_discharge(void){
SN_ALWAYSON->P2_AFIO0=0;
SN_ALWAYSON->P2_AFIO1=0;
SN_ALWAYSON->P2_AFIO2=0;
SN_GPIO2->DIR|=31998u;SN_GPIO2->BCLR=31998u;SN_GPIO1->BSET=1u<<12;sn34_board_analog_pins();}
static inline void sn34_board_scan_input(void){SN_GPIO2->DIR&=~31998u;}
static inline void sn34_board_read_adc(uint16_t *data,volatile const uint32_t *regs){
data[1]=regs[1];data[2]=regs[2];data[3]=regs[3];data[4]=regs[4];data[5]=regs[5];data[6]=regs[6];data[7]=regs[7];data[14]=regs[14];}
static inline void sn34_board_rgb_pins(void){
SN_GPIO1->BSET=1u<<4;SN_GPIO1->DIR|=1u<<4;
HAL_GPIO_SetAFIO(SN_GPIO1,1u<<15,GPIO_P115_SPI_MO1);
HAL_GPIO_SetAFIO(SN_GPIO1,1u<<13,GPIO_P113_SPI_SCK1);
}

static const uint8_t sn34_adc_phase_count[]={9,5};
static const uint32_t sn34_adc_phase_sequence[][4]={
{0x3020101u,0x7060504u,0xeu,0x0u},
{0x3020101u,0x4u,0x0u,0x0u},
};
static inline void sn34_scatter_adc_phase(uint16_t *raw,const uint16_t *adc,unsigned phase){switch(phase){
case 0:
raw[0]=adc[1];raw[1]=adc[2];raw[2]=adc[3];raw[3]=adc[4];raw[4]=adc[5];raw[5]=adc[6];raw[6]=adc[7];raw[7]=adc[14];break;
case 1:
raw[8]=adc[1];raw[9]=adc[2];raw[10]=adc[3];raw[11]=adc[4];raw[12]=adc[5];raw[13]=adc[6];raw[14]=adc[7];raw[15]=adc[14];break;
}}
#define SN34_ADC_INITIAL_SEQUENCE {1,2,3,4,5,6,7,14}
