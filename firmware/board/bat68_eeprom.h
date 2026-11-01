// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
void bat68_eeprom_init(void);
int bat68_eeprom_save(void);
int bat68_eeprom_save_step(void);
bool bat68_eeprom_dirty(void);
uint32_t bat68_eeprom_sequence(void);
extern uint32_t bat68_eeprom_revision;
