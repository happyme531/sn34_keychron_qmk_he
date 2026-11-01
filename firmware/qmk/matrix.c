// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "platform.h"
extern matrix_row_t matrix[MATRIX_ROWS];
static uint16_t scan_depth;
void matrix_init_custom(void) { bat68_he_init(); }
bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    (void)current_matrix; // Keychron HE updates the upstream raw_matrix.
    if(scan_depth++) { --scan_depth; return 0; }
    bool changed=bat68_he_scan(); --scan_depth;
    return changed;
}
bool bat68_matrix_released(void) {
    for(unsigned r=0;r<MATRIX_ROWS;r++) if(matrix[r]) return false;
    return true;
}
void bat68_matrix_snapshot(uint16_t rows[6]) {
    for(unsigned r=0;r<MATRIX_ROWS;r++) rows[r]=matrix_get_row(r);
}
