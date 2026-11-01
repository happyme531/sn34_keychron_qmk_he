// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "platform_deps.h"
#include "host_driver.h"
#include "matrix.h"
#include "sn34_eeprom.h"
bool sn34_matrix_released(void);
bool sn34_physical_released(void);
void sn34_matrix_snapshot(matrix_row_t rows[MATRIX_ROWS]);
bool sn34_he_scan(void);
void sn34_he_init(void);
void sn34_host_init(void);
void sn34_host_task(void);
bool sn34_host_ready(void);
unsigned sn34_host_queued(void);
void sn34_raw_hid_receive(uint8_t *data,uint8_t length);
void sn34_indicators_init(void);
void sn34_indicators_task(void);
extern uint32_t sn34_report_overflows;
extern host_driver_t sn34_host_driver;
int sn34_usb_send(unsigned interface,const void *data,unsigned length);
int sn34_usb_receive(unsigned interface,void *data,unsigned size);
bool sn34_usb_configured(void);
bool sn34_usb_suspended(void);
void sn34_usb_diagnostics(uint8_t out[24]);
void sn34_usb_set_last_boot(const void *data);
bool sn34_usb_boot_protocol(void);
void sn34_eeprom_task(void);
void sn34_eeprom_request_save(void);
void sn34_storage_diagnostics(uint8_t out[32]);
bool sn34_storage_released(void);
void sn34_he_raw_receive(uint8_t *data,uint8_t length);
int sn34_diagnostic(const uint8_t *request,uint8_t *response);
