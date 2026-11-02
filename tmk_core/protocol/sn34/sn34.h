// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "host_driver.h"

#define SN34_USB_BOOT 0
#define SN34_USB_SHARED 1
#ifndef SN34_OTA_ENABLE
#define SN34_OTA_ENABLE 0
#endif
#if SN34_OTA_ENABLE
#define SN34_USB_OTA 2
#define SN34_USB_RAW 3
#else
#define SN34_USB_OTA 255
#define SN34_USB_RAW 2
#endif
#define SN34_HID_INTERFACES (SN34_USB_RAW + 1)
#ifdef XINPUT_ENABLE
#define SN34_USB_XINPUT SN34_HID_INTERFACES
#define SN34_USB_INTERFACE_COUNT (SN34_HID_INTERFACES + 1)
#else
#define SN34_USB_XINPUT 255
#define SN34_USB_INTERFACE_COUNT SN34_HID_INTERFACES
#endif

void sn34_host_init(void);
void sn34_host_task(void);
bool sn34_host_ready(void);
extern host_driver_t sn34_host_driver;
int sn34_usb_send(unsigned interface,const void *data,unsigned length);
int sn34_usb_receive(unsigned interface,void *data,unsigned size);
bool sn34_usb_configured(void);
bool sn34_usb_suspended(void);
void sn34_usb_set_last_boot(const void *data);
int native_usb_init(void);
void native_usb_task(void);
extern uint8_t native_keyboard_leds;
