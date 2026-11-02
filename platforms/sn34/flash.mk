# SPDX-License-Identifier: GPL-2.0-or-later
UV ?= uv
SN34_FLASHER ?= sonixflasher
SN34_FLASH_ARGS ?=

.PHONY: flash
flash: $(BUILD_DIR)/$(TARGET).bin
	$(UV) run util/sn34/flash.py $(BUILD_DIR)/$(TARGET).elf --keyboard $(KEYBOARD) --flasher "$(SN34_FLASHER)" $(SN34_FLASH_ARGS)
