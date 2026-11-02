# SPDX-License-Identifier: GPL-2.0-or-later
ANALOG_MATRIX_I2C_SRC =
ANALOG_MATRIX_EEPROM_SRC = drivers/analog/keychron_he/calibration.c
ANALOG_MATRIX_SCAN_SRC = drivers/analog/adc_mux/sn34_adc_mux.c drivers/analog/keychron_he/matrix.c
ANALOG_MATRIX_USB_SRC = drivers/analog/keychron_he/raw_hid.c
include keyboards/keychron/common/analog_matrix/analog_matrix.mk
SRC += keyboards/keychron/common/nkro.c keyboards/keychron/common/keychron_raw_hid.c
SN34_HAL_SRC += sn34f28x_hal_adc.c
EXTRAINCDIRS += drivers/analog/adc_mux drivers/analog/keychron_he keyboards/keychron/common/analog_matrix keyboards/keychron/common
