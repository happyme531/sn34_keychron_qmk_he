// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "board_config.h"
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
#define configUSE_PCD_PERIPHERAL 1
#define configUSE_IWDG_PERIPHERAL 1
#define configUSE_IWDG_REGISTER_CALLBACKS 0
#include "hal_pcd.h"
#include "hal_iwdg.h"
#define configUSE_DMA_PERIPHERAL 1
#define configUSE_DMA_REGISTER_CALLBACKS 1
#include "hal_dma.h"
#define configUSE_SPI_PERIPHERAL 1
#define configUSE_SPI_REGISTER_CALLBACKS 0
#define configUSE_SPI_BLOCKING 0
#define configUSE_SPI_NONBLOCKING_IT 0
#define configUSE_SPI_NONBLOCKING_DMA 1
#include "hal_spi.h"
#define configUSE_ADC_PERIPHERAL 1
#define configUSE_ADC_NONBLOCKING_IT 1
#define configUSE_ADC_NONBLOCKING_DMA 0
#define configUSE_ADC_REGISTER_CALLBACKS 0
#include "hal_adc.h"
