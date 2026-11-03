// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Launcher effect IDs belong to the configurator adapter, not USB transport.
#ifdef RGB_MATRIX_ENABLE
#include "rgb_matrix.h"
static const uint8_t sn34_rgb_wire_to_core[51] = {
    [0 ... 50] = 255, [0] = 0,
#define SN34_RGB_EFFECT(name, wire) [wire] = RGB_MATRIX_##name,
#include "rgb_protocol.inc"
#undef SN34_RGB_EFFECT
};
static const uint8_t sn34_rgb_core_to_wire[RGB_MATRIX_EFFECT_MAX] = {
    [0] = 0,
#define SN34_RGB_EFFECT(name, wire) [RGB_MATRIX_##name] = wire,
#include "rgb_protocol.inc"
#undef SN34_RGB_EFFECT
};
#else
static const uint8_t sn34_rgb_wire_to_core[] = {0};
static const uint8_t sn34_rgb_core_to_wire[] = {0};
#endif
