// SPDX-License-Identifier: GPL-2.0-or-later
// BAT68 board wiring, with the ADC initialized by the official SONiX HAL.
#include "sn34f28x_hal.h"
#include "native.h"
#include "mailbox.h"
#include "bat68_scan.h"
#if BAT68_QMK_PLATFORM
#include "scan.generated.h"
#endif

static ADC_Handle_T adc;
volatile uint16_t native_raw[96];
volatile uint32_t native_scan_frames;
volatile uint8_t native_scan_phase;
static uint16_t completed_raw[96];
#if BAT68_QMK_PLATFORM
static uint16_t spare_raw[96];
uint16_t *volatile native_scan_work=(uint16_t*)native_raw;
static uint16_t *volatile published_raw=completed_raw;
static const uint16_t *volatile leased_raw;
bool native_scan_acquire(const uint16_t **raw,uint32_t *frame){
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t current=native_scan_frames;
    bool changed=current!=*frame;
    if(changed){leased_raw=published_raw;*raw=published_raw;*frame=current;}
    __set_PRIMASK(saved);return changed;
}
void native_scan_release(void){
    uint32_t saved=__get_PRIMASK();__disable_irq();leased_raw=0;__set_PRIMASK(saved);
}
#endif
volatile uint32_t native_adc_cycles,native_adc_calls,native_adc_max_cycles;
volatile uint8_t native_scan_mode=1;
#if BAT68_QMK_PLATFORM
static volatile uint8_t requested_mode=7;
#else
static volatile uint8_t requested_mode=1;
#endif
int native_scan_configure(unsigned mode){
    if(mode!=0 && mode!=1 && mode!=3 && mode!=7)return -1;
    requested_mode=mode;return 0;
}
bool native_scan_snapshot(uint16_t raw[96],uint32_t *frame){
#if BAT68_QMK_PLATFORM
    const uint16_t *source;
    if(!native_scan_acquire(&source,frame))return false;
    for(unsigned i=0;i<96;i++)raw[i]=source[i];
    native_scan_release();return true;
#else
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t current=native_scan_frames;
    bool changed=current!=*frame;
    if(changed){
        for(unsigned i=0;i<96;i++)raw[i]=completed_raw[i];
        *frame=current;
    }
    __set_PRIMASK(saved);return changed;
#endif
}

static void analog_pins(void){
    // P2.1..7 and P2.10..14 are ADC pins (AFIO function 12). The same
    // pins are briefly pulled low between scans to gate the Hall front end.
    SN_ALWAYSON->P2_AFIO0=0x18c63180;
    SN_ALWAYSON->P2_AFIO1=0x18c0018c;
    SN_ALWAYSON->P2_AFIO2=0x318c;
}
void native_set_mux_phase(unsigned phase){
    if(phase>=8)return;
    if(phase&1u)SN_GPIO2->BSET=0x200u;else SN_GPIO2->BCLR=0x200u;
    SN_GPIO0->BSET=(phase>>1)&3u;
    SN_GPIO0->BCLR=(~(phase>>1))&3u;
}
void HAL_ADC_MspInit(ADC_Handle_T *handle){
    (void)handle;__HAL_RCC_ADC0_CLK_ENABLE();__HAL_RCC_ADC0_RESET();
    // Analog front-end setting observed on the running board, independent
    // of the SDK's internal ADC offset calibration.
    SN_ADC0->MISC_b.XTEST=8;
    NVIC_ClearPendingIRQ(ADC0_IRQn);NVIC_SetPriority(ADC0_IRQn,2);
}
int native_scan_init(void){
    SN_GPIO0->DIR|=3u;SN_GPIO2->DIR|=0x200u;SN_GPIO1->DIR|=0x1000u;
    SN_GPIO2->PULLEN&=~0x7cfeu;
    SN_GPIO2->DIR&=~0x7cfeu;
    analog_pins();native_set_mux_phase(0);SN_GPIO1->BCLR=0x1000u;
    adc.instance=SN_ADC0;adc.init.conv_mode=ADC_CONVMODE_SINGLE_SCAN;
    adc.init.scan_ch_num=15;adc.init.autopwdn=HAL_DISABLE;adc.init.pre_clock=5;
    NATIVE_MAILBOX[12]=2;
    if(HAL_ADC_Init(&adc)!=HAL_OK)return -1;
    NATIVE_MAILBOX[12]=3;
    ADC_Timing_T timing={.power_en_time=32,.hold_time=2};
    if(HAL_ADC_ConfigTiming(&adc,&timing)!=HAL_OK)return -2;
    if(HAL_ADC_SelectRefOption(&adc,ADC_REF_VDD_GND)!=HAL_OK)return -3;
    static const uint8_t sequence[15]={11,10,13,12,2,1,4,3,6,5,14,7,13,12,11};
    for(unsigned i=0;i<15;i++){
        ADC_Channel_T channel={.channel=sequence[i],.rank=i+1};
        if(HAL_ADC_ConfigChannel(&adc,&channel)!=HAL_OK)return -4;
    }
    NATIVE_MAILBOX[12]=4;
    if(HAL_ADC_Start_IT(&adc)!=HAL_OK)return -5;
    // HAL enables both per-channel EOC and whole-scan interrupts. This board
    // handler consumes a complete scan, so mask per-channel EOC sources.
    SN_ADC0->EOCIE=0;
    SN_ADC0->EOCIS=0x3ffffu;
    SN_ADC0->IE=1;
    NVIC_EnableIRQ(ADC0_IRQn);
    return 0;
}
static void start_phase(void){
    native_set_mux_phase(native_scan_phase);SN_GPIO1->BCLR=0x1000u;
    if(!native_scan_phase && requested_mode!=native_scan_mode){
        // Channel 10 needs the initial dummy channel-11 conversion after
        // changing mux. Removing it produced a large offset on the board.
        // Preserve it and all twelve final channel conversions.
        static const uint8_t compact[]={11,10,2,1,4,3,6,5,14,7,13,12,11};
        static const uint8_t original[]={11,10,13,12,2,1,4,3,6,5,14,7,13,12,11};
        const uint8_t *seq=(requested_mode&2)?compact:original;
        unsigned count=(requested_mode&2)?13:15;
        SN_ADC0->SQR0=seq[0]|((uint32_t)seq[1]<<8)|((uint32_t)seq[2]<<16)|((uint32_t)seq[3]<<24);
        SN_ADC0->SQR1=seq[4]|((uint32_t)seq[5]<<8)|((uint32_t)seq[6]<<16)|((uint32_t)seq[7]<<24);
        SN_ADC0->SQR2=seq[8]|((uint32_t)seq[9]<<8)|((uint32_t)seq[10]<<16)|((uint32_t)seq[11]<<24);
        SN_ADC0->SQR3=count==15?seq[12]|((uint32_t)seq[13]<<8)|((uint32_t)seq[14]<<16):seq[12];
        SN_ADC0->CTRL_b.SCANNUM=count-1;native_scan_mode=requested_mode;
    }
#if BAT68_QMK_PLATFORM
    if(native_scan_mode==7){
        const uint32_t *sequence=bat68_adc_phase_sequence[native_scan_phase];
        SN_ADC0->SQR0=sequence[0];SN_ADC0->SQR1=sequence[1];SN_ADC0->SQR2=sequence[2];
        SN_ADC0->CTRL_b.SCANNUM=bat68_adc_phase_count[native_scan_phase]-1;
    }
#endif
    SN_ADC0->CTRL_b.SWSTART=1;
}
void ADC0_IRQHandler(void){
    if(!(SN_ADC0->RIS&1u))return;
    // USB has higher priority. Snapshot both counters atomically, otherwise
    // a USB IRQ between these reads can be counted twice and make a short
    // main-task exclusive interval underflow.
    uint32_t saved=__get_PRIMASK();__disable_irq();
    uint32_t started=DWT->CYCCNT,usb_started=native_usb_irq_cycles;
    __set_PRIMASK(saved);
    SN_ADC0->RIS=3;
    SN_ALWAYSON->P2_AFIO0=0;SN_ALWAYSON->P2_AFIO1=0;SN_ALWAYSON->P2_AFIO2=0;
    SN_GPIO2->DIR|=0x7cfeu;SN_GPIO2->BCLR=0x7cfeu;SN_GPIO1->BSET=0x1000u;
    analog_pins();
    uint16_t data[18];
    volatile const uint32_t *registers=(volatile const uint32_t*)SN_ADC0;
    if(native_scan_mode){
        // Read each live channel once, with constant register offsets.
        data[1]=registers[1];data[2]=registers[2];data[3]=registers[3];data[4]=registers[4];
        data[5]=registers[5];data[6]=registers[6];data[7]=registers[7];
        data[10]=registers[10];data[11]=registers[11];data[12]=registers[12];
        data[13]=registers[13];data[14]=registers[14];
    }else for(unsigned i=0;i<18;i++)data[i]=(uint16_t)registers[i];
    unsigned phase=native_scan_phase;
    bool pipelined=native_scan_mode!=0;
#if BAT68_QMK_PLATFORM
    uint16_t *work=native_scan_work;
#else
    uint16_t *work=(uint16_t*)native_raw;
#endif
    if(!pipelined)bat68_scatter_adc_phase(work,data,phase);
    SN_GPIO2->DIR&=~0x7cfeu;
    native_scan_phase=(phase+1)&7u;
    start_phase();
    if(pipelined){
        // All channel results are captured. Start the next conversion before
        // scattering/copying RAM, overlapping CPU work with ADC conversion.
        bat68_scatter_adc_phase(work,data,phase);
    }
    if(!native_scan_phase){
#if BAT68_QMK_PLATFORM
        // Publish by pointer. Never recycle the consumer's leased frame;
        // when HE is delayed the other two buffers keep the newest frame.
        __DMB();published_raw=work;
        uint16_t *next=(uint16_t*)native_raw;
        if(next==work || next==leased_raw)next=completed_raw;
        if(next==work || next==leased_raw)next=spare_raw;
        native_scan_work=next;
#else
        for(unsigned i=0;i<96;i++)completed_raw[i]=native_raw[i];
#endif
        native_scan_frames++;NATIVE_MAILBOX[10]=native_scan_frames;
    }
    saved=__get_PRIMASK();__disable_irq();
    uint32_t elapsed=DWT->CYCCNT-started-(native_usb_irq_cycles-usb_started);
    native_adc_cycles+=elapsed;native_adc_calls++;
    if(elapsed>native_adc_max_cycles)native_adc_max_cycles=elapsed;
    __set_PRIMASK(saved);
}
