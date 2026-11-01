// SPDX-License-Identifier: GPL-2.0-or-later
// Persistent keymap storage, independent of the keyboard engine and transport.
#pragma once
#include <stdbool.h>
#include <stdint.h>
void qmk_settings_init(void *keymap);
void qmk_settings_changed(void);
int qmk_settings_save(const void *keymap);
uint32_t qmk_settings_sequence(void);
uint8_t qmk_settings_slot(void);
bool qmk_settings_dirty(void);
