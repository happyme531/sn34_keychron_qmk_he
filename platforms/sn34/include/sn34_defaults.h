// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// SN34F280 platform defaults. Boards define overrides before including this file.
#ifndef FAST_TIMER_T_SIZE
#define FAST_TIMER_T_SIZE 32
#endif
#ifndef SN34_CLOCK_HZ
#define SN34_CLOCK_HZ 192000000
#endif
#ifndef SN34_PLL_NS
#define SN34_PLL_NS 64
#endif
#ifndef SN34_PLL_FS
#define SN34_PLL_FS RCC_PLL_DIV4
#endif
#ifndef SN34_RGB_SPI_DIVIDER
#define SN34_RGB_SPI_DIVIDER 31
#endif
#ifndef SN34_ADC_PRE_CLOCK
#define SN34_ADC_PRE_CLOCK 5
#endif
#ifndef SN34_POWER_EN_TIME
#define SN34_POWER_EN_TIME 32
#endif
#ifndef SN34_HOLD_TIME
#define SN34_HOLD_TIME 2
#endif
#ifndef SN34_XTEST
#define SN34_XTEST 8
#endif

#ifndef SN34_APP_ORIGIN
#define SN34_APP_ORIGIN 0x0
#endif
#if SN34_APP_ORIGIN != 0
#error "SN34F280 retained bootloader requires an application at User-ROM offset zero"
#endif
#ifndef SN34_APP_SIZE
#define SN34_APP_SIZE 0x7e000
#endif
#ifndef SN34_PAGE_SIZE
#define SN34_PAGE_SIZE 0x200
#endif
#ifndef SN34_BOOT_USER_OFFSET
#define SN34_BOOT_USER_OFFSET 0x2000
#endif
#ifndef SN34_RAM_ORIGIN
#define SN34_RAM_ORIGIN 0x20000000
#endif
#ifndef SN34_RAM_SIZE
#define SN34_RAM_SIZE 0x28000
#endif
#ifndef SN34_BSS_LIMIT
#define SN34_BSS_LIMIT 0x20024000
#endif
#ifndef SN34_STACK_TOP
#define SN34_STACK_TOP (SN34_RAM_ORIGIN + SN34_RAM_SIZE)
#endif
#ifndef SN34_FOOTER_PAGE
#define SN34_FOOTER_PAGE (SN34_APP_ORIGIN + SN34_APP_SIZE - SN34_PAGE_SIZE)
#endif
#ifndef SN34_FOOTER_ADDRESS
#define SN34_FOOTER_ADDRESS (SN34_APP_ORIGIN + SN34_APP_SIZE - 4)
#endif
#ifndef SN34_FOOTER_MAGIC
#define SN34_FOOTER_MAGIC 0xaaaa5555
#endif
#ifndef SN34_EEPROM_SIZE
#define SN34_EEPROM_SIZE (SN34_EEPROM_BANK_SIZE - SN34_PAGE_SIZE)
#endif
#ifndef SN34_EEPROM_LEGACY_VERSIONS
#define SN34_EEPROM_LEGACY_VERSIONS 0
#endif
#ifndef SN34_EEPROM_END
#define SN34_EEPROM_END (SN34_EEPROM_BANK1 + SN34_EEPROM_BANK_SIZE)
#endif
#ifndef SN34_CODE_LIMIT
#define SN34_CODE_LIMIT SN34_EEPROM_BANK0
#endif
