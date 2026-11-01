#pragma once
#include <stdint.h>

#define SN34_RAW_SLOTS 96
#define SN34_MUX_PHASES 8

/* ADC channel data registers, narrowed to u16 as in the stock ISR.
 * Each of eight mux phases updates 12 slots in the 96-slot snapshot.
 * Inactive slots are intentionally retained across phases.
 */
void sn34_scatter_adc_phase(uint16_t raw[SN34_RAW_SLOTS],
                            const uint16_t adc[18], uint8_t phase);

/* Electrical position is slot * 8 + group. Only groups 0..5 exist.
 * This differs from the layout/action index in the ROM lookup table.
 */
int sn34_electrical_to_raw(uint8_t electrical);
