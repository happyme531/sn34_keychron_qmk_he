// SPDX-License-Identifier: GPL-2.0-or-later
// BAT68 WS2812: original SPI1 timing (3 MHz, four encoded bits per LED bit),
// driven by DMA1 channel 0. Physical order remains a board-validation item.
#include "quantum.h"
#include "rgb_matrix.h"
#include "analog_matrix.h"
#include "sn34f28x_hal.h"
#include "ll_gpio_afio.h"
#include "rgb.generated.h"
enum { RESET_BYTES=120,FRAME_BYTES=RESET_BYTES*2+RGB_MATRIX_LED_COUNT*12 };
static SPI_Handle_T rgb_spi;
static DMA_Handle_T rgb_dma;
static uint8_t colors[RGB_MATRIX_LED_COUNT][3],encoded[FRAME_BYTES];
static volatile bool busy;
static bool initialized;
uint32_t sn34_rgb_frames,sn34_rgb_errors;

void HAL_DMA_MspInit(DMA_Handle_T *h){
    if(h!=&rgb_dma)return;
    __HAL_RCC_DMA1_CLK_ENABLE();__HAL_RCC_DMA1_RESET();
    NVIC_SetPriority(DMA1_CH0_IRQn,3);NVIC_ClearPendingIRQ(DMA1_CH0_IRQn);NVIC_EnableIRQ(DMA1_CH0_IRQn);
}
void DMA1_CH0_IRQHandler(void){HAL_DMA_IRQHandler(&rgb_dma);}
void HAL_SPI_MspInit(SPI_Handle_T *h){
    if(h!=&rgb_spi)return;
    __HAL_RCC_SSP1_CLK_ENABLE();__HAL_RCC_SSP1_RESET();__HAL_RCC_SET_SSP1_CLKSEL(RCC_SPI_CLKSEL_HCLK);
    // P1.4 is held at the same high level as the observed original board.
    SN_GPIO1->BSET=1u<<4;SN_GPIO1->DIR|=1u<<4;
    HAL_GPIO_SetAFIO(SN_GPIO1,GPIO_PIN_15,GPIO_P115_SPI_MO1);
    HAL_GPIO_SetAFIO(SN_GPIO1,GPIO_PIN_13,GPIO_P113_SPI_SCK1);
}
void HAL_SPI_TxCpltCallback(SPI_Handle_T *h){if(h==&rgb_spi){busy=false;sn34_rgb_frames++;}}
void HAL_SPI_ErrorCallback(SPI_Handle_T *h){if(h==&rgb_spi){busy=false;sn34_rgb_errors++;}}
static void init(void){
    rgb_dma.instance=SN_DMA1;
    rgb_dma.init=(DMA_Init_T){.channel=DMA_CHANNEL_0,.ch_xfer_mode=DMA_MEMORY_TO_PERIPH,
        .ch_priority=DMA_PRIORITY_LOW,.ch_fifo_th=DMA_FIFO_TH_1,.ch_sync=HAL_ENABLE,
        .src_burst=DMA_SRC_BURST_1,.src_width=DMA_XFR_WIDTH_8BITS,.src_addr_mode=DMA_ADDR_MODE_INC,
        .src_ahb_master=DMA_AHB_MASTER_MATRIX,.dst_rs=DMA_RS1_SSP1_TX,.dst_width=DMA_XFR_WIDTH_8BITS,
        .dst_addr_mode=DMA_ADDR_MODE_FIXED,.dst_ahb_master=DMA_AHB_MASTER_PERIPH};
    if(HAL_DMA_Init(&rgb_dma)!=HAL_OK){sn34_rgb_errors++;return;}
    rgb_spi.instance=(SN_SPI0_Type*)SN_SPI1;rgb_spi.hdmatx=&rgb_dma;
    rgb_spi.init=(SPI_Init_T){.frame_format=SPI_FFMT_SPI,.mode=SPI_MODE_MASTER,.data_size=8,
        .fs_polarity=SPI_FS_POLARITY_LOW,.clk_polarity=SPI_CLK_POLARITY_LOW,.clk_phase=SPI_CLK_PHASE_1EDGE,
        .sclk_div=31,.first_bit=SPI_FIRST_BIT_MSB,.tx_default=0};
    if(HAL_SPI_Init(&rgb_spi)!=HAL_OK){sn34_rgb_errors++;return;}
    initialized=true;
}
static void set_color(int index,uint8_t r,uint8_t g,uint8_t b){
    if(index<0 || index>=RGB_MATRIX_LED_COUNT)return;
    colors[index][0]=g;colors[index][1]=r;colors[index][2]=b;
}
static void set_all(uint8_t r,uint8_t g,uint8_t b){for(unsigned i=0;i<RGB_MATRIX_LED_COUNT;i++)set_color(i,r,g,b);}
static void flush(void){
    if(!initialized || busy)return;
    static const uint8_t lookup[]={0x88,0x8e,0xe8,0xee};
    unsigned at=RESET_BYTES;
    for(unsigned i=0;i<RGB_MATRIX_LED_COUNT;i++)for(unsigned c=0;c<3;c++){
        unsigned v=colors[i][c];
        for(int shift=6;shift>=0;shift-=2)encoded[at++]=lookup[(v>>shift)&3];
    }
    busy=true;
    if(HAL_SPI_Transmit_DMA(&rgb_spi,encoded,sizeof(encoded))!=HAL_OK){busy=false;sn34_rgb_errors++;}
}
const rgb_matrix_driver_t rgb_matrix_driver={.init=init,.set_color=set_color,.set_color_all=set_all,.flush=flush};
bool rgb_matrix_indicators_kb(void){analog_matrix_indicator();return rgb_matrix_indicators_user();}
