// SPDX-License-Identifier: GPL-2.0-or-later
// This optional HE hook shares the core translation unit, preserving the
// measured flatten/inlining behavior while keeping board mapping here.
#include "board.generated.h"
__attribute__((flatten))
void sn34_analog_update_frame(const uint16_t samples[SN34_SAMPLE_COUNT]) {
    extern matrix_row_t analog_raw_matrix[MATRIX_ROWS];
    for (unsigned i = 0; i < SN34_KEY_COUNT; i++) {
        unsigned slot = board_keys[i].matrix_slot, r = slot / MATRIX_COLS, c = slot % MATRIX_COLS;
        update_raw_value(r, c, samples[board_keys[i].raw_slot]);
        if (analog_matrix_get_key_state(r, c)) analog_raw_matrix[r] |= 1u << c;
    }
}
