# SPDX-License-Identifier: GPL-2.0-or-later
SN34_ROOT := $(CURDIR)
-include .sn34-local.mk
SN34_BOARD_DIR := keyboards/$(KEYBOARD)/board
$(foreach dep,SN34_SDK_DIR SN34_DFP_DIR SN34_CMSIS_DIR,$(if $($(dep)),,$(error Set $(dep) in the environment or .sn34-local.mk)))
MCU_FLASH_SIZE := 504
SN34_LINKER_SCRIPT := $(INTERMEDIATE_OUTPUT)/sn34.ld
SN34_HID_SOURCE := $(INTERMEDIATE_OUTPUT)/sn34/usbd_hid.c
OPT = 2
SRC += $(addprefix platforms/sn34/sn34f28x/,startup.S clock.c timebase.c syscalls.c setup.c flash.c)
SRC += $(addprefix $(SN34_SDK_DIR)/Peripherals/Source/,sn34f28x_hal_gpio.c sn34f28x_hal_scu.c sn34f28x_hal_flash.c sn34f28x_hal_flash_ex.c sn34f28x_hal_rcc.c sn34f28x_hal_iwdg.c)
SRC += $(addprefix $(SN34_SDK_DIR)/Peripherals/Source/,$(SN34_HAL_SRC))
SRC := $(filter-out $(SN34_EXCLUDE_SRC),$(SRC))
EXTRAINCDIRS += $(SN34_BOARD_DIR) platforms/sn34/include
SN34_SYSTEM_INCLUDES = $(SN34_SDK_DIR)/Com $(SN34_SDK_DIR)/../../Board $(SN34_SDK_DIR)/Peripherals/Include $(SN34_SDK_DIR)/Peripherals/Source $(SN34_DFP_DIR) $(SN34_CMSIS_DIR)/CMSIS/Core/Include
COMPILEFLAGS += -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=softfp
COMPILEFLAGS += -ffreestanding -fno-builtin -fno-delete-null-pointer-checks -ffunction-sections -fdata-sections -fshort-enums
CFLAGS += $(COMPILEFLAGS) --specs=nano.specs $(addprefix -isystem ,$(SN34_SYSTEM_INCLUDES)) -include $(SN34_ROOT)/platforms/sn34/include/sn34f28x_hal_conf.h
CXXFLAGS += $(COMPILEFLAGS) --specs=nano.specs $(addprefix -isystem ,$(SN34_SYSTEM_INCLUDES)) -fno-exceptions
ASFLAGS += $(COMPILEFLAGS)
# QMK links with ALL_CFLAGS, which already applies nano.specs exactly once.
$(BUILD_DIR)/$(TARGET).elf: LDFLAGS = $(COMPILEFLAGS) -nostartfiles --specs=nosys.specs -Wl,--gc-sections -Wl,-Map,$(BUILD_DIR)/$(TARGET).map -T$(SN34_LINKER_SCRIPT) $(EXTRALDFLAGS)
TOOLCHAIN ?= arm-none-eabi-
CC = $(CC_PREFIX) $(TOOLCHAIN)gcc
OBJCOPY = $(TOOLCHAIN)objcopy
OBJDUMP = $(TOOLCHAIN)objdump
SIZE = $(TOOLCHAIN)size
AR = $(TOOLCHAIN)ar
NM = $(TOOLCHAIN)nm
HEX = $(OBJCOPY) -O ihex
BIN = $(OBJCOPY) -O binary
EEP =
FIRMWARE_FORMAT = bin
# Keep SDK fixes in the build tree; the external SDK remains untouched.
$(SN34_HID_SOURCE): $(SN34_SDK_DIR)/Middlewares/Source/USB_Device/Class/HID/usbd_hid.c platforms/sn34/hid.patch
	@mkdir -p $(@D)
	@sed 's/\r$$//' $< > $@.tmp
	@patch --silent --batch --forward --fuzz=0 --reject-file=- $@.tmp < platforms/sn34/hid.patch
	@mv $@.tmp $@

$(SN34_LINKER_SCRIPT): platforms/sn34/sn34f28x/application.ld.S $(SN34_BOARD_DIR)/board_config.h
	@mkdir -p $(@D)
	$(CC) -E -P -x c -I$(SN34_BOARD_DIR) $< -o $@
$(BUILD_DIR)/$(TARGET).elf: $(SN34_LINKER_SCRIPT)

bin: $(BUILD_DIR)/$(TARGET).bin sizeafter
