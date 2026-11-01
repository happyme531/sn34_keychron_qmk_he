# SPDX-License-Identifier: GPL-2.0-or-later
ifeq ($(strip $(MCU)),SN34F280)
    PLATFORM_KEY = sn34
    MCU = cortex-m4
    MCU_ARCH = ARM
    MCU_FAMILY = SN34F2
    MCU_SERIES = SN34F28x
endif
