// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
// Outside both the bridge state and native .data/.bss; retained across a core
// reset for diagnosis by the bridge's bounded snapshot command.
#if BAT68_QMK_PLATFORM
#define NATIVE_MAILBOX ((volatile uint32_t*)0x20027fc0u)
#else
#define NATIVE_MAILBOX ((volatile uint32_t*)0x20011000)
#endif
