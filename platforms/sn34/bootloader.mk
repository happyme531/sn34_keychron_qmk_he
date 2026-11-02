# SPDX-License-Identifier: GPL-2.0-or-later
BOOTLOADER_TYPE = custom
FIRMWARE_FORMAT = bin
ifneq ($(strip $(BOOTLOADER)),custom)
    $(error SN34 currently supports BOOTLOADER = custom)
endif
