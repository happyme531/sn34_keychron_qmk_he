# SPDX-License-Identifier: GPL-2.0-or-later
SRC += drivers/eeprom/sn34_banked.c drivers/eeprom/sn34_storage.c
SRC += drivers/eeprom/sn34_flash.c
SN34_EXCLUDE_SRC += eeprom_driver.c
EXTRAINCDIRS += drivers/eeprom
