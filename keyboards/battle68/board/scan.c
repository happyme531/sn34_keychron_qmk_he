/* Register-independent part of BAT68 V1.10 ADC0_IRQHandler at 0x760.
 * HFD24MH001 details are not assumed here; this follows observed board wiring.
 */
#include "sn34_scan.h"
void sn34_scatter_adc_phase(uint16_t raw[SN34_RAW_SLOTS],
                            const uint16_t adc[18], uint8_t phase) {
    if (phase >= SN34_MUX_PHASES) return;
    unsigned upper = phase >> 2;
    uint16_t *out = raw + upper * 16u + (phase & 3u) * 2u;
    // Fixed board wiring: avoid a nested lookup/index loop in every phase
    // interrupt (eight interrupts per complete scan).
    out[0]=adc[10+upper];out[1]=adc[11-upper];
    out[8]=adc[12+upper];out[9]=adc[13-upper];
    out[32]=adc[1+upper];out[33]=adc[2-upper];
    out[40]=adc[3+upper];out[41]=adc[4-upper];
    out[64]=adc[5+upper];out[65]=adc[6-upper];
    out[72]=adc[upper?14:7];out[73]=adc[upper?7:14];
}

int sn34_electrical_to_raw(uint8_t electrical) {
    unsigned group = electrical & 7u;
    unsigned slot = electrical >> 3;
    if (group >= 6 || slot >= 16) return -1;
    return (int)(group * 16u + slot);
}
