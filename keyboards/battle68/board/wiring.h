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
if(phase&(1u<<0)){SN_GPIO2->BSET=1u<<9;}else{SN_GPIO2->BCLR=1u<<9;}
uint32_t mux_p0=(((phase>>1)&1u)<<0)|(((phase>>2)&1u)<<1);SN_GPIO0->BSET=mux_p0;SN_GPIO0->BCLR=mux_p0^3u;
}
static inline void sn34_board_scan_pins_init(void){
SN_GPIO2->DIR|=1u<<9;
SN_GPIO0->DIR|=1u<<0;
SN_GPIO0->DIR|=1u<<1;
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
data[1]=regs[1];data[2]=regs[2];data[3]=regs[3];data[4]=regs[4];data[5]=regs[5];data[6]=regs[6];data[7]=regs[7];data[10]=regs[10];data[11]=regs[11];data[12]=regs[12];data[13]=regs[13];data[14]=regs[14];}
static inline void sn34_board_rgb_pins(void){
SN_GPIO1->BSET=1u<<4;SN_GPIO1->DIR|=1u<<4;
HAL_GPIO_SetAFIO(SN_GPIO1,1u<<15,GPIO_P115_SPI_MO1);
HAL_GPIO_SetAFIO(SN_GPIO1,1u<<13,GPIO_P113_SPI_SCK1);
}

static const uint8_t sn34_adc_phase_count[]={8,9,9,7,10,12,10,10};
static const uint32_t sn34_adc_phase_sequence[][4]={
{0x401020bu,0x70e0603u,0x0u,0x0u},
{0x401020bu,0xe050603u,0x7u,0x0u},
{0x401020bu,0xe050603u,0x7u,0x0u},
{0x301020bu,0x70506u,0x0u,0x0u},
{0x1020a0bu,0x5060304u,0xb0cu,0x0u},
{0x1020a0bu,0x5060304u,0xb0c0d0eu,0x0u},
{0x1020a0bu,0xd070e03u,0xb0cu,0x0u},
{0x1020a0bu,0xd070e04u,0xb0cu,0x0u},
};
static inline void sn34_scatter_adc_phase(uint16_t *raw,const uint16_t *adc,unsigned phase){switch(phase){
case 0:
raw[0]=adc[10];raw[1]=adc[11];raw[8]=adc[12];raw[9]=adc[13];raw[32]=adc[1];raw[33]=adc[2];raw[40]=adc[3];raw[41]=adc[4];raw[64]=adc[5];raw[65]=adc[6];raw[72]=adc[7];raw[73]=adc[14];break;
case 1:
raw[2]=adc[10];raw[3]=adc[11];raw[10]=adc[12];raw[11]=adc[13];raw[34]=adc[1];raw[35]=adc[2];raw[42]=adc[3];raw[43]=adc[4];raw[66]=adc[5];raw[67]=adc[6];raw[74]=adc[7];raw[75]=adc[14];break;
case 2:
raw[4]=adc[10];raw[5]=adc[11];raw[12]=adc[12];raw[13]=adc[13];raw[36]=adc[1];raw[37]=adc[2];raw[44]=adc[3];raw[45]=adc[4];raw[68]=adc[5];raw[69]=adc[6];raw[76]=adc[7];raw[77]=adc[14];break;
case 3:
raw[6]=adc[10];raw[7]=adc[11];raw[14]=adc[12];raw[15]=adc[13];raw[38]=adc[1];raw[39]=adc[2];raw[46]=adc[3];raw[47]=adc[4];raw[70]=adc[5];raw[71]=adc[6];raw[78]=adc[7];raw[79]=adc[14];break;
case 4:
raw[16]=adc[11];raw[17]=adc[10];raw[24]=adc[13];raw[25]=adc[12];raw[48]=adc[2];raw[49]=adc[1];raw[56]=adc[4];raw[57]=adc[3];raw[80]=adc[6];raw[81]=adc[5];raw[88]=adc[14];raw[89]=adc[7];break;
case 5:
raw[18]=adc[11];raw[19]=adc[10];raw[26]=adc[13];raw[27]=adc[12];raw[50]=adc[2];raw[51]=adc[1];raw[58]=adc[4];raw[59]=adc[3];raw[82]=adc[6];raw[83]=adc[5];raw[90]=adc[14];raw[91]=adc[7];break;
case 6:
raw[20]=adc[11];raw[21]=adc[10];raw[28]=adc[13];raw[29]=adc[12];raw[52]=adc[2];raw[53]=adc[1];raw[60]=adc[4];raw[61]=adc[3];raw[84]=adc[6];raw[85]=adc[5];raw[92]=adc[14];raw[93]=adc[7];break;
case 7:
raw[22]=adc[11];raw[23]=adc[10];raw[30]=adc[13];raw[31]=adc[12];raw[54]=adc[2];raw[55]=adc[1];raw[62]=adc[4];raw[63]=adc[3];raw[86]=adc[6];raw[87]=adc[5];raw[94]=adc[14];raw[95]=adc[7];break;
}}
#define SN34_ADC_INITIAL_SEQUENCE {11,10,13,12,2,1,4,3,6,5,14,7,13,12,11}
