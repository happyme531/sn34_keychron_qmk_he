# SPDX-License-Identifier: GPL-2.0-or-later
VPATH += platforms/sn34/include
EXTRAINCDIRS += tmk_core/protocol/sn34
EXTRAINCDIRS += $(SN34_SDK_DIR)/Middlewares/Include $(SN34_SDK_DIR)/Middlewares/Source/USB_Device/Core $(SN34_SDK_DIR)/Middlewares/Source/USB_Device/Class/HID
SRC += tmk_core/protocol/sn34/lifecycle.c tmk_core/protocol/sn34/usb.c tmk_core/protocol/sn34/host.c
SRC += $(addprefix $(SN34_SDK_DIR)/Peripherals/Source/,sn34f28x_hal_pcd.c sn34f28x_ll_otgpe.c)
SRC += $(addprefix $(SN34_SDK_DIR)/Middlewares/Source/USB_Device/Core/,usbd_core.c usbd_ctlreq.c usbd_ioreq.c)
SRC += $(SN34_HID_SOURCE)
ifeq ($(strip $(XINPUT_ENABLE)),yes)
SRC += tmk_core/protocol/sn34/xinput.c
OPT_DEFS += -DXINPUT_ENABLE
endif
ifeq ($(strip $(SN34_OTA_ENABLE)),yes)
OPT_DEFS += -DSN34_OTA_ENABLE=1
endif

# Vendor sources keep their existing warnings; owned firmware remains -Werror.
$(foreach source,$(filter $(SN34_SDK_DIR)/%.c,$(SRC)) $(SN34_HID_SOURCE),$(eval $(INTERMEDIATE_OUTPUT)/$(source:.c=.o): FILE_SPECIFIC_CFLAGS += -Wno-error))
