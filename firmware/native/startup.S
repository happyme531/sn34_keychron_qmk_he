// SPDX-License-Identifier: GPL-2.0-or-later
.syntax unified
.thumb
.cpu cortex-m4
.section .vectors,"a",%progbits
.global native_vectors
native_vectors:
    .word __stack_top
    .word native_trial_entry
    .rept 14
    .word native_default_handler
    .endr
    .rept 3
    .word native_default_handler
    .endr
#if BAT68_COLD_INIT
    .word SCU_IRQHandler
#else
    .word native_default_handler
#endif
    .rept 14
    .word native_default_handler
    .endr
#if BAT68_ENABLE_SCAN
    .word ADC0_IRQHandler
#else
    .word native_default_handler
#endif
#if BAT68_QMK_PLATFORM
    .rept 37
    .word native_default_handler
    .endr
    .word DMA1_CH0_IRQHandler
    .rept 20
#else
    .rept 58
#endif
    .word native_default_handler
    .endr
    .word USB_HS_IRQHandler
    .rept 18
    .word native_default_handler
    .endr

.section .text.entry,"ax",%progbits
.global native_trial_entry
.type native_trial_entry,%function
.thumb_func
native_trial_entry:
    cpsid i
    ldr r0,=__stack_top
    msr msp,r0
    movs r0,#0
    msr control,r0
    isb
    b native_reset
.size native_trial_entry,.-native_trial_entry

.global native_default_handler
.type native_default_handler,%function
.thumb_func
native_default_handler:
    tst lr,#4
    ite eq
    mrseq r0,msp
    mrsne r0,psp
    mov r1,lr
    mrs r2,ipsr
    b native_fault
.size native_default_handler,.-native_default_handler
