// SPDX-License-Identifier: GPL-2.0-or-later
.syntax unified
.thumb
.cpu cortex-m4
.section .text.hook,"ax",%progbits
.global probe_entry
.type probe_entry,%function
.thumb_func
probe_entry:
    push.w {r0-r3,r12,lr}
    bl qmk_bridge_task
    bl qmk_bridge_command
    cmp r0,#0
    bne 1f
    bl probe_handle
    cmp r0,#0
    bne 1f
    pop.w {r0-r3,r12,lr}
    push.w {r3-r11,lr}
    b.w stock_dispatch_resume
1:
    pop.w {r0-r3,r12,lr}
    bx lr
.size probe_entry,.-probe_entry

.section .text.init_entry,"ax",%progbits
.global qmk_init_entry
.type qmk_init_entry,%function
.thumb_func
qmk_init_entry:
    push {r4,lr}
    ldr r4,=0x40e9
    blx r4
    bl qmk_bridge_init
    pop {r4,pc}
.size qmk_init_entry,.-qmk_init_entry

.section .text.sender_gate,"ax",%progbits
.global stock_sender_gate
.type stock_sender_gate,%function
.thumb_func
stock_sender_gate:
    push.w {r0-r3,r12,lr}
    bl qmk_keyboard_owned
    cmp r0,#0
    bne 2f
    pop.w {r0-r3,r12,lr}
    push {r4,lr}
    ldr r0,=0x2000040b
    b.w stock_sender_resume
2:
    pop.w {r0-r3,r12,lr}
    bx lr
.size stock_sender_gate,.-stock_sender_gate
