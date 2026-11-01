// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "Middleware_USBD.h"
extern USBD_Class_t sn34_xinput_class;
int sn34_xinput_send(const void *data,unsigned length);
HAL_Status_T sn34_xinput_vendor(USBD_SetupReq_t *req,uint8_t *data,uint16_t *length);
