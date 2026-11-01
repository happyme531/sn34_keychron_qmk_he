# SPDX-License-Identifier: GPL-2.0-or-later
MCU = SN34F280
SRC += indicators.c diagnostics.c
BOOTLOADER = custom
CUSTOM_MATRIX = lite
# This pinned schema does not expose "none" as a named debounce option.
# Select the existing upstream implementation explicitly; no board copy.
DEBOUNCE_TYPE = custom
SRC += $(QUANTUM_DIR)/debounce/none.c
EEPROM_DRIVER = custom
RGB_MATRIX_ENABLE = yes
RGB_MATRIX_DRIVER = custom
NKRO_ENABLE = yes
EXTRAKEY_ENABLE = yes
MOUSEKEY_ENABLE = yes
VIA_ENABLE = yes
RAW_ENABLE = yes
JOYSTICK_ENABLE = yes
JOYSTICK_DRIVER = digital
TAP_DANCE_ENABLE = yes
COMBO_ENABLE = yes
LTO_ENABLE = no
BOOTMAGIC_ENABLE = no
