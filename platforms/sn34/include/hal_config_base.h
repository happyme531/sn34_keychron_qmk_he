// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#define HAL_EHS_INR_DS 0
#ifndef HAL_EHS_FREQ_MHZ
#define HAL_EHS_FREQ_MHZ 12
#endif
#define __EHS_FREQ (HAL_EHS_FREQ_MHZ*1000000UL)
#define __IHRC_FREQ 12000000UL
#define HAL_ILRC_FREQ 32000UL
#define configUSE_RCC_PERIPHERAL 1
#define configUSE_FLASH_PERIPHERAL 1
#define configUSE_FLASH_BLOCKING 1
#define configUSE_FLASH_NONBLOCKING_IT 0
#define configUSE_FLASH_REGISTER_CALLBACKS 0
#define ASSERT_PARAM(expr) ((void)0U)
#ifndef __weak
#define __weak __attribute__((weak))
#endif
#include "hal_systick.h"
#include "hal_scu.h"
#include "hal_gpio.h"
#include "hal_rcc.h"
#include "hal_flash.h"
