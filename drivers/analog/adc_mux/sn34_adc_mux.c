// SPDX-License-Identifier: GPL-2.0-or-later
// Target-generated wiring and phases, with the ADC initialized by SONiX HAL.
#include "sn34f28x_hal.h"
#include "native.h"
#include "mailbox.h"
#include "hardware.generated.h"
#include "scan.generated.h"

static ADC_Handle_T adc;
volatile uint16_t native_raw[SN34_SAMPLE_COUNT];
volatile uint32_t native_scan_frames;
volatile uint8_t native_scan_phase;
static uint16_t completed_raw[SN34_SAMPLE_COUNT];
static uint16_t spare_raw[SN34_SAMPLE_COUNT];
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
volatile uint32_t native_adc_cycles,native_adc_calls,native_adc_max_cycles;
volatile uint8_t native_scan_mode=1;
static volatile uint8_t requested_mode=7;
int native_scan_configure(unsigned mode){
    if(mode!=0 && mode!=1 && mode!=3 && mode!=7)return -1;
    requested_mode=mode;return 0;
}
bool native_scan_snapshot(uint16_t raw[SN34_SAMPLE_COUNT],uint32_t *frame){
    const uint16_t *source;
    if(!native_scan_acquire(&source,frame))return false;
    for(unsigned i=0;i<SN34_SAMPLE_COUNT;i++)raw[i]=source[i];
    native_scan_release();return true;
}

void native_set_mux_phase(unsigned phase){
    if(phase<SN34_MUX_PHASES)sn34_board_mux_phase(phase);
}
void HAL_ADC_MspInit(ADC_Handle_T *handle){
    (void)handle;__HAL_RCC_ADC0_CLK_ENABLE();__HAL_RCC_ADC0_RESET();
    // Analog front-end setting observed on the running board, independent
    // of the SDK's internal ADC offset calibration.
    SN_ADC0->MISC_b.XTEST=SN34_XTEST;
    NVIC_ClearPendingIRQ(ADC0_IRQn);NVIC_SetPriority(ADC0_IRQn,2);
}
int native_scan_init(void){
    sn34_board_scan_pins_init();sn34_board_analog_pins();native_set_mux_phase(0);sn34_board_sample_gate();
    adc.instance=SN_ADC0;adc.init.conv_mode=ADC_CONVMODE_SINGLE_SCAN;
    adc.init.scan_ch_num=sizeof((uint8_t[])SN34_ADC_INITIAL_SEQUENCE);adc.init.autopwdn=HAL_DISABLE;adc.init.pre_clock=SN34_ADC_PRE_CLOCK;
    NATIVE_MAILBOX[12]=2;
    if(HAL_ADC_Init(&adc)!=HAL_OK)return -1;
    NATIVE_MAILBOX[12]=3;
    ADC_Timing_T timing={.power_en_time=SN34_POWER_EN_TIME,.hold_time=SN34_HOLD_TIME};
    if(HAL_ADC_ConfigTiming(&adc,&timing)!=HAL_OK)return -2;
    if(HAL_ADC_SelectRefOption(&adc,ADC_REF_VDD_GND)!=HAL_OK)return -3;
    static const uint8_t sequence[]=SN34_ADC_INITIAL_SEQUENCE;
    for(unsigned i=0;i<sizeof(sequence);i++){
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
    native_set_mux_phase(native_scan_phase);sn34_board_sample_gate();
    if(!native_scan_phase && requested_mode!=native_scan_mode){
        // Channel 10 needs the initial dummy channel-11 conversion after
        // changing mux. Removing it produced a large offset on the board.
        // Preserve it and all twelve final channel conversions.
        static const uint8_t compact[]=SN34_ADC_COMPACT_SEQUENCE;
        static const uint8_t original[]=SN34_ADC_INITIAL_SEQUENCE;
        const uint8_t *seq=(requested_mode&2)?compact:original;
        unsigned count=(requested_mode&2)?sizeof(compact):sizeof(original);
        uint32_t ranks[4]={0};
        for(unsigned i=0;i<count;i++)ranks[i/4]|=(uint32_t)seq[i]<<((i%4)*8);
        SN_ADC0->SQR0=ranks[0];SN_ADC0->SQR1=ranks[1];SN_ADC0->SQR2=ranks[2];SN_ADC0->SQR3=ranks[3];
        SN_ADC0->CTRL_b.SCANNUM=count-1;native_scan_mode=requested_mode;
    }
    if(native_scan_mode==7){
        const uint32_t *sequence=sn34_adc_phase_sequence[native_scan_phase];
        SN_ADC0->SQR0=sequence[0];SN_ADC0->SQR1=sequence[1];SN_ADC0->SQR2=sequence[2];SN_ADC0->SQR3=sequence[3];
        SN_ADC0->CTRL_b.SCANNUM=sn34_adc_phase_count[native_scan_phase]-1;
    }
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
    sn34_board_scan_discharge();
    uint16_t data[18];
    volatile const uint32_t *registers=(volatile const uint32_t*)SN_ADC0;
    if(native_scan_mode){
        sn34_board_read_adc(data,registers);
    }else for(unsigned i=0;i<18;i++)data[i]=(uint16_t)registers[i];
    unsigned phase=native_scan_phase;
    bool pipelined=native_scan_mode!=0;
    uint16_t *work=native_scan_work;
    if(!pipelined)sn34_scatter_adc_phase(work,data,phase);
    sn34_board_scan_input();
    native_scan_phase=(phase+1)%SN34_MUX_PHASES;
    start_phase();
    if(pipelined){
        // All channel results are captured. Start the next conversion before
        // scattering/copying RAM, overlapping CPU work with ADC conversion.
        sn34_scatter_adc_phase(work,data,phase);
    }
    if(!native_scan_phase){
        // Publish by pointer. Never recycle the consumer's leased frame;
        // when HE is delayed the other two buffers keep the newest frame.
        __DMB();published_raw=work;
        uint16_t *next=(uint16_t*)native_raw;
        if(next==work || next==leased_raw)next=completed_raw;
        if(next==work || next==leased_raw)next=spare_raw;
        native_scan_work=next;
        native_scan_frames++;NATIVE_MAILBOX[10]=native_scan_frames;
    }
    saved=__get_PRIMASK();__disable_irq();
    uint32_t elapsed=DWT->CYCCNT-started-(native_usb_irq_cycles-usb_started);
    native_adc_cycles+=elapsed;native_adc_calls++;
    if(elapsed>native_adc_max_cycles)native_adc_max_cycles=elapsed;
    __set_PRIMASK(saved);
}
