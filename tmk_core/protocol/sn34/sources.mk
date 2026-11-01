# SPDX-License-Identifier: GPL-2.0-or-later
SRC += tmk_core/protocol/sn34/lifecycle.c tmk_core/protocol/sn34/usb.c tmk_core/protocol/sn34/host.c
ifeq ($(strip $(SN34_XINPUT_ENABLE)),yes)
SRC += tmk_core/protocol/sn34/xinput.c
endif
