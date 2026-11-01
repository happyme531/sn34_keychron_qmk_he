.syntax unified
.thumb
.cpu cortex-m4
#include "profile.h"
.section .text.hook,"ax",%progbits
.global probe_entry
.extern stock_dispatch_resume
.type probe_entry,%function
.thumb_func
probe_entry:
    push.w {r0-r3, r12, lr}
    bl probe_handle
    cmp r0, #0
    bne 1f
    pop.w {r0-r3, r12, lr}
    /* Reproduce exactly the four overwritten stock instruction bytes. */
#if BAT68_VERSION == 118
    push.w {r3-r11, lr}
#else
    push {r3-r7, lr}
    ldr r0, =0x20000361
#endif
    b.w stock_dispatch_resume
1:
    pop.w {r0-r3, r12, lr}
    bx lr
.size probe_entry, .-probe_entry
