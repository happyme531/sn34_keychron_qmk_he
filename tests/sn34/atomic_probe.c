// SPDX-License-Identifier: GPL-2.0-or-later
// Linked only into the minimal verification keymap.
#include "atomic_util.h"

static uint32_t early_return(void) {
    ATOMIC_BLOCK_RESTORESTATE { return __get_PRIMASK(); }
    return 0xff;
}

uint32_t sn34_test_atomic(uint32_t initially_disabled) {
    uint32_t saved = __get_PRIMASK(), result;
    __set_PRIMASK(initially_disabled);
    ATOMIC_BLOCK_RESTORESTATE {
        result = __get_PRIMASK();
        ATOMIC_BLOCK_RESTORESTATE { result |= __get_PRIMASK() << 1; }
        result |= __get_PRIMASK() << 2;
    }
    result |= __get_PRIMASK() << 3;
    result |= early_return() << 4;
    result |= __get_PRIMASK() << 5;
    ATOMIC_BLOCK_FORCEON {
        result |= __get_PRIMASK() << 6;
        break;
    }
    result |= __get_PRIMASK() << 7;
    __set_PRIMASK(saved);
    return result;
}
