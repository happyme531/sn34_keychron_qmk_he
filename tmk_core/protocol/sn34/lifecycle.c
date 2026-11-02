// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34.h"
#include "native.h"
#ifdef RGB_MATRIX_ENABLE
#include "rgb_matrix.h"
#endif

void bootloader_jump(void) { native_boot_requested = 1; }
void mcu_reset(void) { native_restart_requested = 1; }
void protocol_setup(void) {
    sn34_host_init();
}
void protocol_pre_init(void) {}
void protocol_post_init(void) { if (native_usb_init()) native_boot_requested = 1; }
void protocol_pre_task(void) { native_usb_task(); sn34_host_task(); }
void protocol_keyboard_task(void) { if (sn34_host_ready()) keyboard_task(); }
void protocol_post_task(void) {
    // Finish an in-flight RGB blackout while keyboard_task is gated by suspend.
#ifdef RGB_MATRIX_ENABLE
    if (sn34_usb_suspended()) rgb_matrix_task();
#endif
    sn34_host_task();
    native_reset_task();
}
