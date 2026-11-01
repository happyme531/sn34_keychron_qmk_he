ENTRY(probe_entry)
stock_dispatch_resume = 0xeb64;
stock_sender_resume = 0x13354;
SECTIONS {
  . = 0x18000;
  .text : { KEEP(*(.text.hook)) KEEP(*(.text.init_entry)) KEEP(*(.text.sender_gate)) *(.text*) *(.rodata*) }
  . = ALIGN(4);
  __data_load = .;
  .data 0x20010000 : AT(__data_load) {
    __data_start = .; *(.data*) . = ALIGN(4); __data_end = .;
  }
  .bss (NOLOAD) : {
    __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .;
  }
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
  ASSERT(__bss_end < 0x20018000, "QMK RAM exceeds its reserved 32 KiB region")
  ASSERT(__data_load + SIZEOF(.data) < 0x30000, "QMK extension exceeds reserved ROM")
}
