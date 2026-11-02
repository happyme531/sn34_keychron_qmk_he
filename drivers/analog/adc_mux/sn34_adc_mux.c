// SPDX-License-Identifier: GPL-2.0-or-later
// Board wiring and phases, with the ADC initialized by SONiX HAL.
#include "sn34f28x_hal.h"
#include "sn34_adc_mux.h"
#include "wiring.h"

static ADC_Handle_T adc;
volatile uint16_t native_raw[SN34_SAMPLE_COUNT];
volatile uint32_t native_scan_frames;
volatile uint8_t native_scan_phase;
static uint16_t completed_raw[SN34_SAMPLE_COUNT];
static uint16_t spare_raw[SN34_SAMPLE_COUNT];
uint16_t *volatile native_scan_work=(uint16_t*)native_raw;
static uint16_t *volatile published_raw=completed_raw;
static const uint16_t *volatile leased_raw;
static bool phase_sequences_active;
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
void HAL_ADC_MspInit(ADC_Handle_T *handle){
    (void)handle;__HAL_RCC_ADC0_CLK_ENABLE();__HAL_RCC_ADC0_RESET();
    // Analog front-end setting observed on the running board, independent
    // of the SDK's internal ADC offset calibration.
    SN_ADC0->MISC_b.XTEST=SN34_XTEST;
    NVIC_ClearPendingIRQ(ADC0_IRQn);NVIC_SetPriority(ADC0_IRQn,2);
}
int native_scan_init(void){
    sn34_board_scan_pins_init();sn34_board_analog_pins();sn34_board_mux_phase(0);sn34_board_sample_gate();
    adc.instance=SN_ADC0;adc.init.conv_mode=ADC_CONVMODE_SINGLE_SCAN;
    adc.init.scan_ch_num=sizeof((uint8_t[])SN34_ADC_INITIAL_SEQUENCE);adc.init.autopwdn=HAL_DISABLE;adc.init.pre_clock=SN34_ADC_PRE_CLOCK;
    if(HAL_ADC_Init(&adc)!=HAL_OK)return -1;
    ADC_Timing_T timing={.power_en_time=SN34_POWER_EN_TIME,.hold_time=SN34_HOLD_TIME};
    if(HAL_ADC_ConfigTiming(&adc,&timing)!=HAL_OK)return -2;
    if(HAL_ADC_SelectRefOption(&adc,ADC_REF_VDD_GND)!=HAL_OK)return -3;
    static const uint8_t sequence[]=SN34_ADC_INITIAL_SEQUENCE;
    for(unsigned i=0;i<sizeof(sequence);i++){
        ADC_Channel_T channel={.channel=sequence[i],.rank=i+1};
        if(HAL_ADC_ConfigChannel(&adc,&channel)!=HAL_OK)return -4;
    }
    if(HAL_ADC_Start_IT(&adc)!=HAL_OK)return -5;
    // HAL enables both per-channel EOC and whole-scan interrupts. This board
    // handler consumes a complete scan, so mask per-channel EOC sources.
    SN_ADC0->EOCIE=0;
    SN_ADC0->EOCIS=0x3ffffu;
    SN_ADC0->IE=1;
    NVIC_EnableIRQ(ADC0_IRQn);
    return 0;
}
static void start_phase(void) {
    sn34_board_mux_phase(native_scan_phase);
    sn34_board_sample_gate();
    // Preserve the original full-channel startup frame, then use per-phase ranks.
    if (!native_scan_phase) phase_sequences_active = true;
    if (phase_sequences_active) {
        const uint32_t *sequence = sn34_adc_phase_sequence[native_scan_phase];
        SN_ADC0->SQR0=sequence[0];SN_ADC0->SQR1=sequence[1];SN_ADC0->SQR2=sequence[2];SN_ADC0->SQR3=sequence[3];
        SN_ADC0->CTRL_b.SCANNUM=sn34_adc_phase_count[native_scan_phase]-1;
    }
    SN_ADC0->CTRL_b.SWSTART=1;
}
void ADC0_IRQHandler(void){
    if(!(SN_ADC0->RIS&1u))return;
    SN_ADC0->RIS=3;
    sn34_board_scan_discharge();
    uint16_t data[18];
    volatile const uint32_t *registers=(volatile const uint32_t*)SN_ADC0;
    sn34_board_read_adc(data,registers);
    unsigned phase=native_scan_phase;
    uint16_t *work=native_scan_work;
    sn34_board_scan_input();
    native_scan_phase=(phase+1)%SN34_MUX_PHASES;
    start_phase();
    // Restart conversion before scattering RAM; the channel results are captured.
    sn34_scatter_adc_phase(work,data,phase);
    if(!native_scan_phase){
        // Publish by pointer. Never recycle the consumer's leased frame;
        // when HE is delayed the other two buffers keep the newest frame.
        __DMB();published_raw=work;
        uint16_t *next=(uint16_t*)native_raw;
        if(next==work || next==leased_raw)next=completed_raw;
        if(next==work || next==leased_raw)next=spare_raw;
        native_scan_work=next;
        native_scan_frames++;
    }
}
