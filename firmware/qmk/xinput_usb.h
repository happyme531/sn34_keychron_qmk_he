// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "Middleware_USBD.h"
extern USBD_Class_t bat68_xinput_class;
int bat68_xinput_send(const void *data,unsigned length);
HAL_Status_T bat68_xinput_vendor(USBD_SetupReq_t *req,uint8_t *data,uint16_t *length);
