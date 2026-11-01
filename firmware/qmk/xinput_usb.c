// SPDX-License-Identifier: GPL-2.0-or-later
// XUSB protocol layout follows Keychron QMK's usb_descriptor.c. It is a
// separate vendor class, not a HID report disguised as an Xbox controller.
#include "xinput_usb.h"
#include "usbd_core.h"
#include "usbd_ioreq.h"
#include <string.h>
static uint8_t descriptor[]={
    9,4,0,0,2,0xff,0x5d,1,0,
    17,0x21,0,1,1,0x25,0x86,0x14,0,0,0,0,0x13,6,8,0,0,
    7,5,0x86,3,32,0,4,7,5,6,3,32,0,4};
static uint8_t compatible[]={40,0,0,0,0,1,4,0,1,0,0,0,0,0,0,0,
    0,1,'X','U','S','B','1','0',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
static uint8_t input[32],output[32];
static volatile bool busy;
static uint8_t interface_id;
static HAL_Status_T init(USBD_Class_t *c){
    interface_id=USBD_Get_Interface(c->pdev,c);if(interface_id==255)return HAL_ERROR;
    if(!USBD_Get_Endpoint(c->pdev,c,USB_DIR_IN,6) || !USBD_Get_Endpoint(c->pdev,c,USB_DIR_OUT,6))return HAL_ERROR;
    descriptor[2]=compatible[16]=interface_id;return HAL_OK;
}
static HAL_Status_T enable(USBD_Class_t *c,USBD_Speed_t speed){
    (void)speed;busy=false;
    if(HAL_PCD_EP_Open(&hPCD,0x86,32,3)!=HAL_OK || HAL_PCD_EP_Open(&hPCD,6,32,3)!=HAL_OK)return HAL_ERROR;
    c->pdev->in_ep[6].is_used=c->pdev->out_ep[6].is_used=1;
    return HAL_PCD_EP_Receive(&hPCD,6,output,32);
}
static HAL_Status_T disable(USBD_Class_t *c){
    busy=false;HAL_PCD_EP_Close(&hPCD,0x86);HAL_PCD_EP_Close(&hPCD,6);
    c->pdev->in_ep[6].is_used=c->pdev->out_ep[6].is_used=0;return HAL_OK;
}
static HAL_Status_T setup(USBD_Class_t *c,USBD_SetupReq_t *r){
    if(r->bRequest==USB_REQ_GET_INTERFACE && r->wIndex==interface_id){
        uint8_t *buf=c->pdev->request_data_buf;*buf=0;return USBD_CtlSendData(c->pdev,buf,1);
    }
    return HAL_ERROR;
}
static HAL_Status_T in(USBD_Class_t *c,uint8_t ep){(void)c;if((ep&15)==6)busy=false;return HAL_OK;}
static HAL_Status_T out(USBD_Class_t *c,uint8_t ep){(void)c;(void)ep;return HAL_PCD_EP_Receive(&hPCD,6,output,32);}
static uint8_t *get_descriptor(USBD_Class_t *c,USBD_Speed_t speed,uint16_t *n){
    (void)c;descriptor[32]=descriptor[39]=speed==USBD_SPEED_HIGH?4:1;*n=sizeof(descriptor);return descriptor;
}
static uint8_t *get_string(USBD_Class_t *c,uint8_t index,uint16_t *n){
    (void)c;if(index!=0xee)return NULL;*n=8;return (uint8_t*)"MSFT100\x20";
}
USBD_Class_t bat68_xinput_class={.Init=init,.DeInit=disable,.Enable=enable,.Disable=disable,.Setup=setup,
    .DataIn=in,.DataOut=out,.GetClassDescriptor=get_descriptor,.GetStringDescriptor=get_string};
int bat68_xinput_send(const void *data,unsigned length){
    USBD_Handle_t *dev=bat68_xinput_class.pdev;
    if(!dev || dev->dev_state!=USBD_STATE_CONFIGURED || busy || length!=20)return -1;
    memcpy(input,data,length);busy=true;
    if(HAL_PCD_EP_Transmit(&hPCD,0x86,input,length)!=HAL_OK){busy=false;return -1;}
    return 0;
}
HAL_Status_T bat68_xinput_vendor(USBD_SetupReq_t *req,uint8_t *data,uint16_t *length){
    if(req->bRequest!=0x20 || req->wIndex!=4 || req->wValue)return HAL_ERROR;
    memcpy(data,compatible,sizeof(compatible));*length=sizeof(compatible);return HAL_OK;
}
