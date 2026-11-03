// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "ll_gpio_afio.h"

// OEM BOOM68-USB V1.10: active-low bank enables, not binary MUX addresses.
static inline void sn34_board_mux_idle(void) {
    SN_GPIO0->BSET = 0xf800u;
    SN_GPIO3->BSET = 3u;
}

static inline void sn34_board_scan_pins_init(void) {
    __HAL_RCC_GPIO_P0_CLK_ENABLE();
    __HAL_RCC_GPIO_P2_CLK_ENABLE();
    __HAL_RCC_GPIO_P3_CLK_ENABLE();
    // Select only the pins used here; preserve unrelated AFIO fields.
    SN_ALWAYSON->P0_AFIO1 &= ~(31u << 25); // P0.11
    SN_ALWAYSON->P0_AFIO2 &= ~0xfffffu;    // P0.12..15
    SN_ALWAYSON->P3_AFIO0 &= ~0x3ffu;     // P3.0..1
    SN_ALWAYSON->P3_AFIO1 &= ~(0x7fffu << 10); // P3.8..10
    sn34_board_mux_idle();
    SN_GPIO0->DIR |= 0xf800u;
    SN_GPIO3->DIR = (SN_GPIO3->DIR | 3u) & ~0x700u;
    SN_GPIO3->PUTYPE |= 0x700u;
    SN_GPIO3->PULLEN |= 0x700u;
    SN_GPIO2->DIR &= ~0xffffu;
    SN_GPIO2->PULLEN &= ~0xffffu;
}

static inline void sn34_board_gpio_init(void) {
    sn34_board_scan_pins_init();
    __HAL_RCC_GPIO_P1_CLK_ENABLE();
    SN_ALWAYSON->P1_AFIO0 &= ~(31u << 20); // P1.4 peripheral enable
    SN_GPIO1->BSET = 1u << 4;
    SN_GPIO1->DIR |= 1u << 4;
}

static inline void sn34_board_analog_pins(void) {
    SN_ALWAYSON->P2_AFIO0 = 0x18c6318cu; // ADC0 channels 0..5
    SN_ALWAYSON->P2_AFIO1 = 0x18c6318cu; // ADC0 channels 6..11
    SN_ALWAYSON->P2_AFIO2 = (SN_ALWAYSON->P2_AFIO2 & ~0xfffffu) | 0x6318cu;
}

static inline void sn34_board_mux_phase(unsigned phase) {
    sn34_board_mux_idle();
    switch (phase) {
        case 0: SN_GPIO0->BCLR = (1u << 13) | (1u << 14); break;
        case 1: SN_GPIO0->BCLR = 1u << 12; break;
        case 2: SN_GPIO3->BCLR = 1u << 0; break;
        case 3: SN_GPIO3->BCLR = 1u << 1; break;
        case 4: SN_GPIO0->BCLR = 1u << 11; break;
    }
}

static inline void sn34_board_sample_gate(void) {
    // OEM selects the next bank before processing the preceding bank. The fast
    // shared scanner has no such work interval, so supply it explicitly here.
    uint32_t start = DWT->CYCCNT;
    while ((uint32_t)(DWT->CYCCNT - start) < BOOM68_BANK_SETTLE_US * (SN34_CLOCK_HZ / 1000000u)) __NOP();
}
// Never ground the ADC inputs here: the OEM only deselects the sensor banks.
static inline void sn34_board_scan_discharge(void) { sn34_board_mux_idle(); }
static inline void sn34_board_scan_input(void) {}
static inline void sn34_board_read_adc(uint16_t *data, volatile const uint32_t *regs) {
    for (unsigned channel = 0; channel < 16; channel++) data[channel] = regs[channel];
}

static inline void sn34_board_rgb_pins(void) {
    SN_GPIO1->BSET = 1u << 4;
    SN_GPIO1->DIR |= 1u << 4;
    HAL_GPIO_SetAFIO(SN_GPIO1, 1u << 15, GPIO_P115_SPI_MO1);
}

// Preserve the OEM's leading channel 10 and trailing internal channel 16.
// Rank 17 lives in SQR4, configured once by HAL; it is constant in every phase.
#define SN34_ADC_INITIAL_SEQUENCE {10,11,9,8,15,14,7,6,5,4,3,2,1,0,13,12,16}
static const uint8_t sn34_adc_phase_count[] = {17,17,17,17,17};
#define BOOM68_ADC_RANKS {0x08090b0au,0x06070e0fu,0x02030405u,0x0c0d0001u}
static const uint32_t sn34_adc_phase_sequence[][4] = {
    BOOM68_ADC_RANKS, BOOM68_ADC_RANKS, BOOM68_ADC_RANKS, BOOM68_ADC_RANKS, BOOM68_ADC_RANKS
};
#undef BOOM68_ADC_RANKS
static inline void sn34_scatter_adc_phase(uint16_t *raw, const uint16_t *adc, unsigned phase) {
    static const uint8_t channels[16] = {9,8,15,14,7,6,5,4,3,2,1,10,13,12,11,0};
    for (unsigned lane = 0; lane < 16; lane++) raw[phase * 16 + lane] = adc[channels[lane]];
}
