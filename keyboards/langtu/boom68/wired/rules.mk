# SPDX-License-Identifier: GPL-2.0-or-later
XINPUT_ENABLE = yes
SN34_OTA_ENABLE = yes
SRC += profiles.c encoder.c
ENCODER_ENABLE = yes
ENCODER_DRIVER = custom
ENCODER_MAP_ENABLE = yes
DEBOUNCE_TYPE = custom
SRC += $(QUANTUM_DIR)/debounce/none.c
EEPROM_DRIVER = vendor
RGB_MATRIX_ENABLE = yes
RGB_MATRIX_DRIVER = custom
NKRO_ENABLE = yes
EXTRAKEY_ENABLE = yes
MOUSEKEY_ENABLE = yes
VIA_ENABLE = yes
RAW_ENABLE = yes
JOYSTICK_ENABLE = yes
JOYSTICK_DRIVER = digital
LTO_ENABLE = no
BOOTMAGIC_ENABLE = no
include drivers/analog/sn34.mk
include drivers/eeprom/sn34.mk
