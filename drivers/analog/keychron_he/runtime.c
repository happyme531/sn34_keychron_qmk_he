// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34_he.h"
#include "sn34.h"
#include "sn34_eeprom.h"
#include "profile.h"

// Called by the board's housekeeping hook. QMK invokes the user hook itself.
void sn34_he_task(void) {
    if (sn34_host_ready()) process_profile_select_combo();
    sn34_eeprom_task(sn34_he_idle());
}
