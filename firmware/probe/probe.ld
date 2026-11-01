ENTRY(probe_entry)
SECTIONS {
    . = 0x00018000;
    .text : { KEEP(*(.text.hook)) *(.text*) *(.rodata*) }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(SIZEOF(.data) == 0, "Extension must not require initialized writable data")
    ASSERT(SIZEOF(.bss) == 0, "Extension must not require a new RAM allocation")
    ASSERT(SIZEOF(.text) < 0x1000, "Diagnostic extension unexpectedly large")
}
