// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34f28x_hal.h"

#if BOOM68_ENCODER_RESOLUTION < 1
#    error "BOOM68_ENCODER_RESOLUTION must be positive"
#endif
static uint8_t previous;
static int8_t movement;

void encoder_driver_init(void) {
    previous = (SN_GPIO3->DATAIN >> 8) & 3u;
    movement = 0;
}

void encoder_driver_task(void) {
    // Full quadrature decoding cancels contact bounce and rejects skipped states.
    static const int8_t delta[16] = {0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};
    uint8_t state = (SN_GPIO3->DATAIN >> 8) & 3u;
    if ((state ^ previous) == 3u) movement = 0;
    else movement += delta[(previous << 2) | state];
    previous = state;
    if (movement >= BOOM68_ENCODER_RESOLUTION || movement <= -BOOM68_ENCODER_RESOLUTION) {
        // OEM idle 11 -> 10 is the clockwise/volume-up direction.
        encoder_queue_event(0, (movement < 0) ^ BOOM68_ENCODER_REVERSE);
        movement = 0;
    }
}
