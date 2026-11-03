# SPDX-License-Identifier: GPL-2.0-or-later
# The HE adapter owns shared sources. Keep driver/feature declarations in
# keyboard rules so QMK's metadata reader sees the actual build choices.
# The pinned QMK schema has no named "none" option; use its existing none.c.
LTO_ENABLE = no
SRC += $(QUANTUM_DIR)/debounce/none.c drivers/analog/keychron_he/runtime.c
include drivers/eeprom/sn34.mk

ANALOG_MATRIX_I2C_SRC =
ANALOG_MATRIX_EEPROM_SRC = drivers/analog/keychron_he/calibration.c
ANALOG_MATRIX_SCAN_SRC = drivers/analog/adc_mux/sn34_adc_mux.c drivers/analog/keychron_he/matrix.c
ANALOG_MATRIX_USB_SRC = drivers/analog/keychron_he/raw_hid.c
include keyboards/keychron/common/analog_matrix/analog_matrix.mk
SRC += keyboards/keychron/common/nkro.c keyboards/keychron/common/keychron_raw_hid.c
SN34_HAL_SRC += sn34f28x_hal_adc.c
EXTRAINCDIRS += drivers/analog/adc_mux drivers/analog/keychron_he keyboards/keychron/common/analog_matrix keyboards/keychron/common
# Inline the scan loop through the public HE API, without source inclusion or
# whole-firmware LTO. Other QMK/SDK translation units retain their normal build.
$(foreach source,drivers/analog/keychron_he/matrix.c $(ANALOG_MATRX_DIR)/analog_matrix.c,$(eval $(INTERMEDIATE_OUTPUT)/$(source:.c=.o): FILE_SPECIFIC_CFLAGS += -flto))
EXTRALDFLAGS += -flto
