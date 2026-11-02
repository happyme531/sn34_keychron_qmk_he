// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>

// User-ROM offsets. The EEPROM wrapper accepts only the configured banks.
int sn34_flash_write_eeprom_page(uint32_t user_offset,const void *data);
// Erase only the unused final application page containing the factory-valid
// footer. After reset into Boot mapping, the retained Bootloader stays in ISP.
int sn34_flash_invalidate_application(void);

int sn34_flash_prepare(void);
// Chip primitive: accepts aligned pages within the application partition.
int sn34_flash_program_user_page(uint32_t user_offset,const void *data);
