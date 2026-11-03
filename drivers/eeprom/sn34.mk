# SPDX-License-Identifier: GPL-2.0-or-later
SRC += drivers/eeprom/sn34_banked.c drivers/eeprom/sn34_storage.c
# Full vendor backend: QMK must invoke its init/erase hooks, without adding
# the generic EEPROM wrappers (the cache implements efficient updates itself).
OPT_DEFS += -DEEPROM_DRIVER
EXTRAINCDIRS += drivers/eeprom
