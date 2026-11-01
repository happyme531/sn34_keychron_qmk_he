# SPDX-License-Identifier: GPL-2.0-or-later
SN34_ROOT := $(CURDIR)
SN34_KEYBOARD := $(KEYBOARD)
SN34_KEYMAP := $(KEYMAP)
SN34_BUILD_DIR ?= $(CURDIR)/.build/sn34/$(KEYBOARD)/$(KEYMAP)
SN34_BUILD_DIR := $(abspath $(SN34_BUILD_DIR))
export SN34_ROOT SN34_KEYBOARD SN34_KEYMAP SN34_BUILD_DIR
export SN34_QMK_BUILD_DIR := $(abspath $(BUILD_DIR))
ALLOW_WARNINGS = yes
SN34_GENERATED := $(SN34_BUILD_DIR)
SN34_UV ?= uv
OPT = 2
SN34_PREPARED := $(shell mkdir -p $(SN34_GENERATED) && $(SN34_UV) run --no-project $(SN34_ROOT)/util/sn34/prepare.py > $(SN34_GENERATED)/prepare.log 2>&1 && printf ready)
ifneq ($(SN34_PREPARED),ready)
    $(error SN34 preparation failed; see $(SN34_GENERATED)/prepare.log)
endif
include $(SN34_GENERATED)/platform_sources.mk
include drivers/analog/sn34.mk
include drivers/eeprom/sn34.mk
include tmk_core/protocol/sn34/sources.mk
SRC += $(SN34_EXTRA_SRC)
SRC += $(addprefix platforms/sn34/sn34f28x/,startup.S clock.c timebase.c runtime.c memory.c ctype.c setup.c flash.c)
SRC += drivers/led/ws2812_sn34.c
SRC := $(filter-out eeprom_driver.c,$(SRC))
EXTRAINCDIRS := $(SN34_EXTRA_INC) $(EXTRAINCDIRS)
OPT_DEFS += -DSN34_QMK_PLATFORM=1 -DSN34_KEYCHRON_HE=1 -DSN34_ENABLE_SCAN=1 -DSN34_ENABLE_KEYBOARD=1
OPT_DEFS += -DSN34_STANDALONE=1 -DSN34_COLD_INIT=1 -DSN34_NATIVE_TIMEBASE=1
COMPILEFLAGS += -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=softfp
COMPILEFLAGS += -ffreestanding -fno-builtin -fno-delete-null-pointer-checks -ffunction-sections -fdata-sections -fshort-enums
CFLAGS += $(COMPILEFLAGS) -Wno-error -Wno-unknown-pragmas -include $(SN34_ROOT)/platforms/sn34/include/sn34f28x_hal_conf.h
CXXFLAGS += $(COMPILEFLAGS) -Wno-error -fno-exceptions
ASFLAGS += $(COMPILEFLAGS)
$(BUILD_DIR)/$(TARGET).elf: LDFLAGS = $(COMPILEFLAGS) -nostdlib -Wl,--gc-sections -Wl,-Map,$(BUILD_DIR)/$(TARGET).map -L$(SN34_GENERATED) -T$(SN34_ROOT)/platforms/sn34/sn34f28x/application.ld -lgcc $(EXTRALDFLAGS)
SN34_CC ?= arm-none-eabi-gcc
export SN34_CC
CC = $(CC_PREFIX) $(SN34_CC)
OBJCOPY = arm-none-eabi-objcopy
OBJDUMP = arm-none-eabi-objdump
SIZE = arm-none-eabi-size
AR = arm-none-eabi-ar
NM = arm-none-eabi-nm
HEX = $(OBJCOPY) -O ihex
BIN = $(OBJCOPY) -O binary
EEP =
FIRMWARE_FORMAT = bin
MCU_FLASH_SIZE = $(SN34_CODE_KIB)
bin: $(BUILD_DIR)/$(TARGET).bin sizeafter

