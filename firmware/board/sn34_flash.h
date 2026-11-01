// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>

// User-ROM offsets, not physical flash addresses. The driver only accepts the
// two keymap pages and never accepts an address in Boot or option memory.
int sn34_flash_write_settings_page(uint32_t user_offset,const void *data);
#if BAT68_KEYCHRON_HE
int sn34_flash_write_eeprom_page(uint32_t user_offset,const void *data);
#endif
// Erase only the unused final application page containing the factory-valid
// footer. After reset into Boot mapping, the retained Bootloader stays in ISP.
int sn34_flash_invalidate_application(void);
int sn34_flash_validate_application(void);
