// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
void sn34_eeprom_init(void);
int sn34_eeprom_save_step(void);
bool sn34_eeprom_dirty(void);
uint32_t sn34_eeprom_version(void);
void sn34_eeprom_task(bool idle);
extern uint32_t sn34_eeprom_revision;
