ENTRY(sn34_reset_entry)
#include "board_config.h"
SECTIONS {
  . = SN34_APP_ORIGIN;
  __rom_origin = .;
  .vectors : { KEEP(*(.vectors)) }
  .text : { KEEP(*(.text.entry)) *(.text*) *(ISR) *(.rodata*) }
  . = ALIGN(8);
  __data_load = .;
  .data SN34_RAM_ORIGIN : AT(__data_load) {
    __data_start = .; *(.data*) . = ALIGN(8); __data_end = .;
  }
  .bss (NOLOAD) : {
    __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .;
  }
  __stack_top = SN34_STACK_TOP;
  __heap_start = __bss_end;
  __heap_end = SN34_BSS_LIMIT;
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
  ASSERT(SN34_PAGE_SIZE == 512, "SN34 Flash requires 512-byte pages")
  ASSERT(SN34_EEPROM_BANK_SIZE > SN34_PAGE_SIZE && SN34_EEPROM_BANK_SIZE % SN34_PAGE_SIZE == 0 && SN34_EEPROM_SIZE + SN34_PAGE_SIZE == SN34_EEPROM_BANK_SIZE, "SN34 EEPROM bank must contain whole payload pages and one header page")
  ASSERT(SN34_EEPROM_BANK0 % SN34_PAGE_SIZE == 0 && SN34_EEPROM_BANK1 % SN34_PAGE_SIZE == 0, "SN34 EEPROM banks must be page aligned")
  ASSERT(SN34_EEPROM_BANK0 + SN34_EEPROM_BANK_SIZE <= SN34_EEPROM_BANK1 || SN34_EEPROM_BANK1 + SN34_EEPROM_BANK_SIZE <= SN34_EEPROM_BANK0, "SN34 EEPROM banks overlap")
  ASSERT(SN34_APP_ORIGIN <= SN34_EEPROM_BANK0 && SN34_APP_ORIGIN <= SN34_EEPROM_BANK1 && SN34_APP_ORIGIN < SN34_CODE_LIMIT && SN34_CODE_LIMIT <= MIN(SN34_EEPROM_BANK0, SN34_EEPROM_BANK1), "SN34 code limit must precede both EEPROM banks")
  ASSERT(MAX(SN34_EEPROM_BANK0, SN34_EEPROM_BANK1) + SN34_EEPROM_BANK_SIZE <= SN34_FOOTER_PAGE, "SN34 EEPROM bank overlaps application footer")
  ASSERT(SN34_EEPROM_END == MAX(SN34_EEPROM_BANK0, SN34_EEPROM_BANK1) + SN34_EEPROM_BANK_SIZE, "SN34 EEPROM end must cover both banks")
  ASSERT(SN34_FOOTER_PAGE % SN34_PAGE_SIZE == 0 && SN34_FOOTER_PAGE + SN34_PAGE_SIZE == SN34_APP_ORIGIN + SN34_APP_SIZE && SN34_FOOTER_ADDRESS == SN34_APP_ORIGIN + SN34_APP_SIZE - 4, "SN34 footer must occupy the final application page")
  ASSERT(SN34_RAM_ORIGIN < SN34_BSS_LIMIT && SN34_BSS_LIMIT < SN34_STACK_TOP && SN34_STACK_TOP <= SN34_RAM_ORIGIN + SN34_RAM_SIZE, "SN34 heap and stack must fit RAM")
  ASSERT(__heap_start + 8192 <= __heap_end, "SN34 target requires 8 KiB for newlib heap and reserved stack headroom")
  ASSERT(__data_load + SIZEOF(.data) < SN34_CODE_LIMIT, "SN34 target code overlaps EEPROM banks")
}

// Expose memory/ABI constants to optional packaging and firmware tests.
#define SN34_VALUE(name) __sn34_##name = SN34_##name;
SN34_VALUE(APP_ORIGIN)
SN34_VALUE(APP_SIZE)
SN34_VALUE(PAGE_SIZE)
SN34_VALUE(BOOT_USER_OFFSET)
SN34_VALUE(EEPROM_BANK_SIZE)
SN34_VALUE(EEPROM_SIZE)
SN34_VALUE(EEPROM_BASE)
SN34_VALUE(EEPROM_MAGIC)
SN34_VALUE(EEPROM_COMMIT)
SN34_VALUE(EEPROM_VERSION)
SN34_VALUE(EEPROM_LEGACY_VERSIONS)
SN34_VALUE(FOOTER_PAGE)
SN34_VALUE(FOOTER_ADDRESS)
SN34_VALUE(FOOTER_MAGIC)
SN34_VALUE(RAM_ORIGIN)
SN34_VALUE(RAM_SIZE)
SN34_VALUE(BSS_LIMIT)
SN34_VALUE(EEPROM_BANK0)
SN34_VALUE(EEPROM_BANK1)
SN34_VALUE(EEPROM_END)
SN34_VALUE(CODE_LIMIT)
SN34_VALUE(STACK_TOP)
#undef SN34_VALUE
