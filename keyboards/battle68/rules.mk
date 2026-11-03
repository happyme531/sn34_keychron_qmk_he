# SPDX-License-Identifier: GPL-2.0-or-later
XINPUT_ENABLE = yes
SN34_OTA_ENABLE = yes
SRC += indicators.c profiles.c compatibility.c
DEBOUNCE_TYPE = custom
EEPROM_DRIVER = vendor
RGB_MATRIX_ENABLE = yes
RGB_MATRIX_DRIVER = custom
NKRO_ENABLE = yes
EXTRAKEY_ENABLE = yes
MOUSEKEY_ENABLE = yes
VIA_ENABLE = yes
JOYSTICK_ENABLE = yes
JOYSTICK_DRIVER = digital
TAP_DANCE_ENABLE = yes
COMBO_ENABLE = yes
BOOTMAGIC_ENABLE = no

include drivers/analog/sn34.mk
