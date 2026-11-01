// SPDX-License-Identifier: GPL-2.0-or-later
// SONiX ADC adapter for Keychron's original analog_matrix and profile modules.
#include "quantum.h"
#include "analog_matrix.h"
#include "profile.h"
#include "game_controller_common.h"
#include "he.h"
#include "hall.generated.h"
#include "eeprom.h"
#include "native.h"

void bootloader_jump(void) { native_boot_requested = 1; }
void mcu_reset(void) { native_restart_requested = 1; }
int abs(int value) { return value < 0 ? -value : value; }

matrix_row_t analog_matrix_mask[MATRIX_ROWS];
matrix_row_t analog_raw_matrix[MATRIX_ROWS], changed_matrix[MATRIX_ROWS];
matrix_row_t raw_matrix[MATRIX_ROWS], virtual_matrix[MATRIX_ROWS];
extern matrix_row_t okmc_matrix[MATRIX_ROWS], game_controller_matrix[MATRIX_ROWS];
uint8_t profile_gobal_mode[PROFILE_COUNT] = {AKM_REGULAR, AKM_RAPID, AKM_REGULAR};
uint16_t default_profiles[PROFILE_COUNT][MATRIX_ROWS][MATRIX_COLS];

void bat68_he_init(void) {
    for (unsigned i = 0; i < BAT68_HALL_KEYS; i++)
        analog_matrix_mask[hall_keys[i].slot / 16] |= 1u << (hall_keys[i].slot % 16);
    bat68_eeprom_init();
    analog_matrix_init();
}

// analog_matrix_init requests eight initial scans. Actual ADC samples only
// become available once startup enables IRQs; calibration runs on fresh frames.
uint8_t matrix_scan(void) { return 0; }
matrix_row_t matrix_get_row(uint8_t row) { return row < MATRIX_ROWS ? virtual_matrix[row] : 0; }
uint8_t matrix_rows(void) { return MATRIX_ROWS; }
uint8_t matrix_cols(void) { return MATRIX_COLS; }
bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    return process_record_profile(keycode, record) && process_record_user(keycode, record);
}

void bat68_he_scan(const uint16_t raw[96], matrix_row_t next[MATRIX_ROWS]) {
    for (unsigned r = 0; r < MATRIX_ROWS; r++) {
        matrix_row_t before = analog_raw_matrix[r];
        analog_raw_matrix[r] = 0;
        for (unsigned c = 0; c < MATRIX_COLS; c++) {
            if (!(analog_matrix_mask[r] & (1u << c))) continue;
            update_raw_value(r, c, raw[r * 16 + c]);
            if (analog_matrix_get_key_state(r, c)) analog_raw_matrix[r] |= 1u << c;
        }
        changed_matrix[r] = before ^ analog_raw_matrix[r];
    }
    analog_matrix_task();
    for (unsigned r = 0; r < MATRIX_ROWS; r++) {
        // socd_action produces raw_matrix. DKS and gamepad typing use their
        // own virtual matrices, as in Keychron's matrix_scan_custom.
        next[r] = virtual_matrix[r] = (raw_matrix[r] | okmc_matrix[r] | game_controller_matrix[r]) & analog_matrix_mask[r];
    }
}

static bool all_released(void) {
    for (unsigned r = 0; r < MATRIX_ROWS; r++) if (analog_raw_matrix[r]) return false;
    return true;
}

// Board transport deliberately exposes a bounded subset of upstream HE
// requests. Native 0xAA commands use byte 2 as a layer/count; 0x7C carries HE
// requests at byte 8 so existing diagnostics and OTA remain compatible.
// Operations: 0=status, 1=select, 2=configure key, 3=save profile, 4=travel,
// 5=reset profile. Coordinates refer to the board's 6x16 logical matrix.
int bat68_he_command(const uint8_t *rx, uint8_t *tx, bool released) {
    if (rx[1] != 0x7c) return 0;
    unsigned op = rx[8], p = rx[9], r = rx[10], c = rx[11];
    tx[2] = 0xff;
    if (op == 0) {
        tx[2] = 16; tx[8] = 1; tx[9] = profile_get_current_index(); tx[10] = PROFILE_COUNT;
        tx[11] = bat68_eeprom_dirty();
        analog_key_config_t *cfg = &profile_get_current()->global;
        tx[12] = cfg->mode; tx[13] = cfg->act_pt; tx[14] = cfg->rpd_trig_sen; tx[15] = cfg->rpd_trig_sen_deact;
        uint32_t sequence = bat68_eeprom_sequence(); memcpy(tx + 16, &sequence, 4);
    } else if (op == 4 && r < MATRIX_ROWS && c < MATRIX_COLS && (analog_matrix_mask[r] & (1u << c))) {
        tx[2] = 4; tx[8] = analog_matrix_get_travel(r, c); tx[9] = analog_matrix_get_key_mode(r, c);
        tx[10] = analog_matrix_get_key_state(r, c);
    } else if (released && all_released() && p < PROFILE_COUNT) {
        if (op == 1) {
            if (profile_select(p, false)) { tx[2] = 1; tx[8] = p; }
        } else if (op == 2 && (rx[12] == AKM_REGULAR || rx[12] == AKM_RAPID) &&
                   rx[13] >= 1 && rx[13] <= 39 && rx[14] >= 1 && rx[14] <= 39 && rx[15] >= 1 && rx[15] <= 39 &&
                   ((r == 0xff && c == 0xff) || (r < MATRIX_ROWS && c < MATRIX_COLS && (analog_matrix_mask[r] & (1u << c))))) {
            uint32_t rows[MATRIX_ROWS] = {0};
            bool global = r == 0xff;
            if (!global) rows[r] = 1u << c;
            if (profile_set_traval(p, rx[12], rx[13], rx[14], rx[15], global, rows)) {
                // Upstream's global setter does not refresh active key state.
                if (p == profile_get_current_index()) update_travel_configs();
                profile_save(p); // Stage for explicit Flash save and dirty reporting.
                tx[2] = 1; tx[8] = 1;
            }
        } else if (op == 3) {
            if (profile_save(p) && bat68_eeprom_save() >= 0) { tx[2] = 1; tx[8] = 1; }
        } else if (op == 5 && profile_reset(p)) {
            if (p == profile_get_current_index()) update_travel_configs();
            tx[2] = 1; tx[8] = 1;
        }
    }
    return 1;
}
