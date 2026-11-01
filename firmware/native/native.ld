ENTRY(native_trial_entry)
SECTIONS {
  . = DEFINED(BAT68_ROM_ORIGIN) ? BAT68_ROM_ORIGIN : 0x30000;
  __rom_origin = .;
  .vectors : { KEEP(*(.vectors)) }
  .text : { KEEP(*(.text.entry)) *(.text*) *(ISR) *(.rodata*) }
  . = ALIGN(8);
  __data_load = .;
  .data 0x20012000 : AT(__data_load) {
    __data_start = .; *(.data*) . = ALIGN(8); __data_end = .;
  }
  .bss (NOLOAD) : {
    __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .;
  }
  __stack_top = 0x20028000;
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
  ASSERT(__bss_end <= 0x20027000, "Native image leaves less than 4 KiB stack")
  ASSERT(__data_load + SIZEOF(.data) < __rom_origin + 0x20000, "Native ROM exceeds its reservation")
}
