// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "platform_deps.h"
#include "host_driver.h"
#include "bat68_eeprom.h"
bool bat68_matrix_released(void);
bool bat68_physical_released(void);
void bat68_matrix_snapshot(uint16_t rows[6]);
bool bat68_he_scan(void);
void bat68_he_init(void);
void bat68_host_init(void);
void bat68_host_task(void);
bool bat68_host_ready(void);
unsigned bat68_host_queued(void);
void bat68_raw_hid_receive(uint8_t *data,uint8_t length);
void bat68_indicators_init(void);
void bat68_indicators_task(void);
extern uint32_t bat68_report_overflows;
extern host_driver_t bat68_host_driver;
enum { BAT68_USB_BOOT=0,BAT68_USB_SHARED=1,BAT68_USB_DIAGNOSTIC=2,BAT68_USB_OTA=3,BAT68_USB_RAW=4 };
int bat68_usb_send(unsigned interface,const void *data,unsigned length);
#define BAT68_USB_XINPUT 5
int bat68_usb_receive(unsigned interface,void *data,unsigned size);
bool bat68_usb_configured(void);
bool bat68_usb_suspended(void);
void bat68_usb_diagnostics(uint8_t out[24]);
void bat68_usb_set_last_boot(const void *data);
bool bat68_usb_boot_protocol(void);
void bat68_eeprom_task(void);
void bat68_eeprom_request_save(void);
void bat68_storage_diagnostics(uint8_t out[32]);
bool bat68_storage_released(void);
void bat68_he_raw_receive(uint8_t *data,uint8_t length);
int bat68_diagnostic(const uint8_t *request,uint8_t *response);
