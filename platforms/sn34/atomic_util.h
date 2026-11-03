// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
#include "sn34f28x_hal.h"

static inline uint32_t sn34_interrupt_lock(void) {
    uint32_t state = __get_PRIMASK();
    __disable_irq();
    return state;
}
static inline void sn34_interrupt_restore(const uint32_t *state) {
    __set_PRIMASK(*state);
}
static inline void sn34_interrupt_enable(const uint32_t *state) {
    (void)state;
    __enable_irq();
}

#define ATOMIC_BLOCK(type) for (type, __ToDo = 1; __ToDo; __ToDo = 0)
#define ATOMIC_RESTORESTATE uint32_t status_save __attribute__((__cleanup__(sn34_interrupt_restore))) = sn34_interrupt_lock()
#define ATOMIC_FORCEON uint32_t status_save __attribute__((__cleanup__(sn34_interrupt_enable))) = sn34_interrupt_lock()
#define ATOMIC_BLOCK_RESTORESTATE ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
#define ATOMIC_BLOCK_FORCEON ATOMIC_BLOCK(ATOMIC_FORCEON)
