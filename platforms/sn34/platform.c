// SPDX-License-Identifier: GPL-2.0-or-later
// Optional board indicators; reset/platform setup live in sn34f28x/setup.c.
__attribute__((weak)) void sn34_indicators_init(void) {}
__attribute__((weak)) void sn34_indicators_task(void) {}
