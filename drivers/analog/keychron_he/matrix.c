// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "analog_matrix.h"
#include "game_controller_common.h"
#include "sn34_he.h"
#include "sn34_adc_mux.h"
#include "sn34_board.h"
#include "sn34_eeprom.h"
#include "sn34.h"
#include "sn34_bootloader.h"
#include "hall_curve.inc"
#include "keys.inc"

// Normalize each key's measured endpoints before inverting the stock magnetic
// response. Profiles and gamepad normalization retain the HE 0..240 range.
// Keep the conversion callable and avoid duplicating its divisions in the loop.
__attribute__((noinline)) uint8_t sn34_hall_convert(uint16_t value, uint16_t zero, uint16_t bottom) {
    if (zero <= bottom || value >= zero) return 0;
    if (value <= bottom) return 240;
    uint32_t adc = ((uint32_t)(zero - value) * 65535u) / (zero - bottom);
    unsigned lo = 0, hi = sizeof(sn34_hall_adc_curve) / sizeof(sn34_hall_adc_curve[0]) - 1;
    unsigned end = hi;
    while (hi - lo > 1) {
        unsigned mid = (lo + hi) / 2;
        if (adc < sn34_hall_adc_curve[mid]) hi = mid;
        else lo = mid;
    }
    uint32_t fraction = ((adc - sn34_hall_adc_curve[lo]) * 256u) / (sn34_hall_adc_curve[hi] - sn34_hall_adc_curve[lo]);
    return ((lo * 256u + fraction) * 240u + end * 128u) / (end * 256u);
}

matrix_row_t analog_matrix_mask[MATRIX_ROWS];
matrix_row_t analog_raw_matrix[MATRIX_ROWS], changed_matrix[MATRIX_ROWS];
matrix_row_t virtual_matrix[MATRIX_ROWS];
extern matrix_row_t raw_matrix[MATRIX_ROWS], matrix[MATRIX_ROWS];
extern matrix_row_t okmc_matrix[MATRIX_ROWS], game_controller_matrix[MATRIX_ROWS];
static uint32_t last_frame;
static uint16_t scan_depth;

void matrix_setup(void) {
    if (!sn34_eeprom_migrate()) sn34_bootloader_enter();
    sn34_he_calibration_init();
    if (native_scan_init()) sn34_bootloader_enter();
}

void matrix_init_custom(void) {
    for (unsigned i = 0; i < SN34_KEY_COUNT; i++)
        analog_matrix_mask[board_keys[i].matrix_slot / MATRIX_COLS] |= 1u << (board_keys[i].matrix_slot % MATRIX_COLS);
    analog_matrix_init();
}

// LTO keeps this hot loop inlined across the HE adapter boundary, without
// including platform implementation fragments in Keychron's core source.
// Keep this loop separate from the larger scan task to bound register pressure.
__attribute__((flatten, noinline)) static void update_frame(const uint16_t *samples) {
    for (unsigned i = 0; i < SN34_KEY_COUNT; i++) {
        unsigned slot = board_keys[i].matrix_slot, r = slot / MATRIX_COLS, c = slot % MATRIX_COLS;
        update_raw_value(r, c, samples[board_keys[i].raw_slot]);
        if (analog_matrix_get_key_state(r, c)) analog_raw_matrix[r] |= 1u << c;
    }
}

static bool scan_frame(void) {
    const uint16_t *samples;
    if (!native_scan_acquire(&samples, &last_frame)) return false;
    matrix_row_t before[MATRIX_ROWS];
    memcpy(before, analog_raw_matrix, sizeof(before));
    memset(analog_raw_matrix, 0, sizeof(analog_raw_matrix));
    update_frame(samples);
    native_scan_release();
    for (unsigned r = 0; r < MATRIX_ROWS; r++) changed_matrix[r] = before[r] ^ analog_raw_matrix[r];
    analog_matrix_task();
    bool changed = false;
    for (unsigned r = 0; r < MATRIX_ROWS; r++) {
        matrix_row_t next = raw_matrix[r] & analog_matrix_mask[r];
        changed |= next != matrix[r];
        raw_matrix[r] = next;
        // DKS dispatches its own actions; virtual activity must not dispatch the
        // physical key's normal keycode a second time through QMK.
        virtual_matrix[r] = next | okmc_matrix[r] | game_controller_matrix[r];
    }
    return changed;
}

bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    (void)current_matrix; // Keychron HE updates the upstream raw_matrix.
    if (scan_depth++) { --scan_depth; return false; }
    bool changed = scan_frame();
    --scan_depth;
    return changed;
}

bool sn34_matrix_released(void) {
    for (unsigned r = 0; r < MATRIX_ROWS; r++) if (matrix[r]) return false;
    return true;
}

bool sn34_physical_released(void) {
    for (unsigned i = 0; i < SN34_KEY_COUNT; i++) {
        unsigned slot = board_keys[i].matrix_slot;
        if (analog_matrix_get_travel(slot / MATRIX_COLS, slot % MATRIX_COLS) > TRAVEL_SCALE) return false;
    }
    return true;
}

bool sn34_he_idle(void) {
    if (!sn34_matrix_released()) return false;
    for (unsigned row = 0; row < MATRIX_ROWS; row++) if (analog_raw_matrix[row]) return false;
    return true;
}

// Keep HE state recovery out of the USB transport. Both reconnect and FIFO
// overflow must clear the controller's internal state as well as its reports.
void sn34_host_reset(void) {
    game_controller_clear();
}
