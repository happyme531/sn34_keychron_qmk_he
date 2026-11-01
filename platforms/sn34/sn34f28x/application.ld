ENTRY(sn34_reset_entry)
INCLUDE sn34_memory.generated.ld
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
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
  ASSERT(__bss_end <= SN34_BSS_LIMIT, "BAT68 requires reserved stack headroom")
  ASSERT(__data_load + SIZEOF(.data) < SN34_CODE_LIMIT, "BAT68 code overlaps EEPROM banks")
}
