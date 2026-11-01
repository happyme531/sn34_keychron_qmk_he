// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic board used only for compile/emulation coverage of shared drivers.
#include "platform.h"
void sn34_indicators_init(void) {}
void sn34_indicators_task(void) {}
int sn34_diagnostic(const uint8_t *request,uint8_t *response) {
    (void)request;
    response[2]=255;
    return 0;
}
