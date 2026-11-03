// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
void sn34_eeprom_init(void);
int sn34_eeprom_save_step(void);
bool sn34_eeprom_dirty(void);
int sn34_flash_write_eeprom_page(uint32_t user_offset, const void *data);
void sn34_eeprom_task(bool idle);
extern uint32_t sn34_eeprom_revision;
