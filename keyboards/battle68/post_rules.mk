# SPDX-License-Identifier: GPL-2.0-or-later
# VIA enables Bootmagic in common_features.mk after board rules are loaded.
# Keep it disabled: this board's (0,0) switch is the physical Fn key.
# The override lives here because QMK's rules.mk metadata parser does not
# understand GNU Make's override keyword.
override BOOTMAGIC_ENABLE = no
include drivers/led/sn34.mk
