// SPDX-License-Identifier: GPL-2.0-or-later
// newlib-nano owns libc and allocation; this platform supplies only heap bounds.
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

extern unsigned char __heap_start[], __heap_end[];
static unsigned char *heap_break;

void *_sbrk(ptrdiff_t increment) {
    if (!heap_break) heap_break = __heap_start;
    if ((increment >= 0 && (uintptr_t)increment > (uintptr_t)(__heap_end - heap_break)) ||
        (increment < 0 && (uintptr_t)(-(increment + 1)) + 1 > (uintptr_t)(heap_break - __heap_start))) {
        errno = ENOMEM;
        return (void *)-1;
    }
    void *previous = heap_break;
    heap_break += increment;
    return previous;
}

// Console output is disabled. SDK diagnostics use newlib's nosys write stub.
int8_t sendchar(uint8_t c) { (void)c; return 0; }
