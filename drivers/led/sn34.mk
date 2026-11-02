# SPDX-License-Identifier: GPL-2.0-or-later
ifeq ($(strip $(RGB_MATRIX_ENABLE)),yes)
SRC += drivers/led/ws2812_sn34.c
SN34_HAL_SRC += sn34f28x_hal_spi.c sn34f28x_hal_dma.c
EXTRAINCDIRS += drivers/led
endif
