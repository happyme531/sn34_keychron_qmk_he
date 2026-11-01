# SPDX-License-Identifier: GPL-2.0-or-later
SRC += drivers/analog/adc_mux/sn34_adc_mux.c
SRC += drivers/analog/keychron_he/adapter.c drivers/analog/keychron_he/matrix.c drivers/analog/keychron_he/raw_hid.c
SN34_HE_DIR := keyboards/keychron/common/analog_matrix
SRC += $(addprefix $(SN34_HE_DIR)/,analog_matrix.c profile.c action_regular_trigger.c action_rapid_trigger.c action_okmc.c action_toggle.c action_socd.c game_controller_common.c action_joystick.c action_xinput.c sqrt.c)
SRC += keyboards/keychron/common/nkro.c keyboards/keychron/common/keychron_raw_hid.c
