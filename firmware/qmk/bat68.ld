ENTRY(native_trial_entry)
INCLUDE bat68_memory.generated.ld
SECTIONS {
  . = BAT68_APP_ORIGIN;
  __rom_origin = .;
  .vectors : { KEEP(*(.vectors)) }
  .text : { KEEP(*(.text.entry)) *(.text*) *(ISR) *(.rodata*) }
  . = ALIGN(8);
  __data_load = .;
  .data BAT68_RAM_ORIGIN : AT(__data_load) {
    __data_start = .; *(.data*) . = ALIGN(8); __data_end = .;
  }
  .bss (NOLOAD) : {
    __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .;
  }
  __stack_top = BAT68_STACK_TOP;
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
  ASSERT(__bss_end <= BAT68_BSS_LIMIT, "BAT68 requires reserved stack headroom")
  ASSERT(__data_load + SIZEOF(.data) < BAT68_CODE_LIMIT, "BAT68 code overlaps EEPROM banks")
}
