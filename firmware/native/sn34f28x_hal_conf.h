// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "../board/sn34f28x_hal_conf.h"
#define configUSE_PCD_PERIPHERAL 1
#define configUSE_IWDG_PERIPHERAL 1
#define configUSE_IWDG_REGISTER_CALLBACKS 0
#include "hal_pcd.h"
#include "hal_iwdg.h"
#if BAT68_QMK_PLATFORM
#define configUSE_DMA_PERIPHERAL 1
#define configUSE_DMA_REGISTER_CALLBACKS 1
#include "hal_dma.h"
#define configUSE_SPI_PERIPHERAL 1
#define configUSE_SPI_REGISTER_CALLBACKS 0
#define configUSE_SPI_BLOCKING 0
#define configUSE_SPI_NONBLOCKING_IT 0
#define configUSE_SPI_NONBLOCKING_DMA 1
#include "hal_spi.h"
#endif
#if BAT68_ENABLE_SCAN
#define configUSE_ADC_PERIPHERAL 1
#define configUSE_ADC_NONBLOCKING_IT 1
#define configUSE_ADC_NONBLOCKING_DMA 0
#define configUSE_ADC_REGISTER_CALLBACKS 0
#include "hal_adc.h"
#endif
