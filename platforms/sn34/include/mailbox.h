// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdint.h>
// Outside both the bridge state and native .data/.bss; retained across a core
// reset for diagnosis by the bridge's bounded snapshot command.
#include "sn34_storage.generated.h"
#define NATIVE_MAILBOX ((volatile uint32_t*)SN34_STACK_TOP)
