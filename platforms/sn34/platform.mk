# SPDX-License-Identifier: GPL-2.0-or-later
ifndef BAT68_ROOT
    $(error BAT68_ROOT is required; build with uv run /path/to/bat68/tools/build_bat68.py)
endif
BAT68_ROOT := $(abspath $(BAT68_ROOT))
BAT68_BUILD_DIR ?= $(BAT68_ROOT)/build/bat68
BAT68_BUILD_DIR := $(abspath $(BAT68_BUILD_DIR))
export BAT68_ROOT BAT68_BUILD_DIR
export BAT68_QMK_DIR := $(CURDIR)
export BAT68_QMK_BUILD_DIR := $(abspath $(BUILD_DIR))
ALLOW_WARNINGS = yes
BAT68_GENERATED := $(BAT68_BUILD_DIR)
BAT68_UV ?= uv
OPT = 2
BAT68_PREPARED := $(shell mkdir -p $(BAT68_GENERATED) && $(BAT68_UV) run $(BAT68_ROOT)/tools/prepare_bat68.py > $(BAT68_GENERATED)/prepare.log 2>&1 && printf ready)
ifneq ($(BAT68_PREPARED),ready)
    $(error BAT68 preparation failed; see $(BAT68_GENERATED)/prepare.log)
endif
include $(BAT68_GENERATED)/platform_sources.mk
SRC += $(BAT68_EXTRA_SRC)
# The cache implements the complete EEPROM API without a variable-size stack
# copy. All production builds use these QMK rules and driver definitions.
SRC := $(filter-out eeprom_driver.c $(QUANTUM_DIR)/via.c,$(SRC))
EXTRAINCDIRS := $(BAT68_EXTRA_INC) $(EXTRAINCDIRS)
QUANTUM_SRC := $(filter-out $(QUANTUM_DIR)/via.c,$(QUANTUM_SRC))
OPT_DEFS += -DBAT68_QMK_PLATFORM=1 -DBAT68_KEYCHRON_HE=1 -DBAT68_ENABLE_SCAN=1 -DBAT68_ENABLE_KEYBOARD=1
OPT_DEFS += -DBAT68_STANDALONE=1 -DBAT68_COLD_INIT=1 -DBAT68_NATIVE_TIMEBASE=1
COMPILEFLAGS += -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=softfp
COMPILEFLAGS += -ffreestanding -fno-builtin -fno-delete-null-pointer-checks -ffunction-sections -fdata-sections -fshort-enums
CFLAGS += $(COMPILEFLAGS) -Wno-error -Wno-unknown-pragmas -include $(BAT68_ROOT)/firmware/native/sn34f28x_hal_conf.h
CXXFLAGS += $(COMPILEFLAGS) -Wno-error -fno-exceptions
ASFLAGS += $(COMPILEFLAGS)
# The freestanding platform supplies memory/math routines. Override the common
# hosted -lm default, retaining compiler runtime support for integer division.
$(BUILD_DIR)/$(TARGET).elf: LDFLAGS = $(COMPILEFLAGS) -nostdlib -Wl,--gc-sections -Wl,-Map,$(BUILD_DIR)/$(TARGET).map -L$(BAT68_GENERATED) -T$(BAT68_ROOT)/firmware/qmk/bat68.ld -lgcc $(EXTRALDFLAGS)
BAT68_CC ?= arm-none-eabi-gcc
export BAT68_CC
CC = $(CC_PREFIX) $(BAT68_CC)
OBJCOPY = arm-none-eabi-objcopy
OBJDUMP = arm-none-eabi-objdump
SIZE = arm-none-eabi-size
AR = arm-none-eabi-ar
NM = arm-none-eabi-nm
HEX = $(OBJCOPY) -O ihex
BIN = $(OBJCOPY) -O binary
EEP =
FIRMWARE_FORMAT = bin
MCU_FLASH_SIZE = $(BAT68_CODE_KIB)

bin: $(BUILD_DIR)/$(TARGET).bin sizeafter
