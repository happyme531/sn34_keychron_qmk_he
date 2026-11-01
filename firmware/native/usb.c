// SPDX-License-Identifier: GPL-2.0-or-later
// Board descriptors and report glue around the unchanged SONiX USB Device/HID
// sources. No proprietary ISP helper library is linked into this USB trial.
#include "Middleware_USBD.h"
#include "native.h"
#include "mailbox.h"
#include <string.h>
static USBD_Handle_t device;
static uint8_t response[64],response_pending;
volatile uint32_t native_usb_irqs;
volatile uint32_t native_usb_irq_cycles;
uint8_t native_keyboard_leds;
static uint8_t last_keyboard_report[8];
static HAL_Status_T get_input(uint8_t idx,uint8_t id,uint8_t *data,uint16_t *length){
    if(idx||id)return HAL_ERROR;
    *length=8;
    memcpy(data,last_keyboard_report,*length);return HAL_OK;
}
static HAL_Status_T set_feature(uint8_t idx,uint8_t id,uint8_t *data,uint16_t length){
    static const uint8_t magic[]={0xaa,0x55,0xa5,0x5a,0xff,0,0x33,0xcc};
    if(idx!=3||id||length<sizeof(magic)||memcmp(data,magic,sizeof(magic)))return HAL_ERROR;
    // Complete EP0 first; the actual transition runs later in main context.
    native_boot_requested=1;return HAL_OK;
}
static uint8_t keyboard_desc[]={
    0x05,0x01,0x09,0x06,0xa1,0x01,0x05,0x07,0x19,0xe0,0x29,0xe7,
    0x15,0,0x25,1,0x75,1,0x95,8,0x81,2,0x95,1,0x75,8,0x81,1,
    0x95,5,0x75,1,0x05,8,0x19,1,0x29,5,0x91,2,0x95,1,0x75,3,0x91,1,
    0x95,6,0x75,8,0x15,0,0x25,0x65,0x05,7,0x19,0,0x29,0x65,0x81,0,0xc0
};
static uint8_t consumer_desc[]={
    0x05,0x0c,0x09,1,0xa1,1,0x15,0,0x26,0xff,3,0x19,0,0x2a,0xff,3,
    0x75,0x10,0x95,1,0x81,0,0xc0
};
static uint8_t vendor_desc[]={
    0x06,0x68,0xff,0x09,0x61,0xa1,1,0x09,0x62,0x15,0,0x26,0xff,0,
    0x75,8,0x95,0x40,0x81,2,0x09,0x63,0x15,0,0x26,0xff,0,0x75,8,0x95,0x40,0x91,2,0xc0
};
static uint8_t isp_desc[]={
    0x06,0x67,0xff,0x09,0x61,0xa1,1,0x09,0x63,0x15,0,0x26,0xff,0,
    0x75,8,0x96,0,0x10,0x91,2,0x09,0x62,0x15,0,0x26,0xff,0,0x75,8,0x95,0x40,0xb1,2,0xc0
};
static USBD_ReportInfo_t reports={
    .intf_num=4,
    .GetInputReport_isr_cb=get_input,
    .SetFeatureReport_isr_cb=set_feature,
    .intf_param={
        {.subclass=1,.protocol=1,.bInEp=1,.InEpNum=1,.in_report_length=8,
         .out_report_length=1,.report_desc_length=sizeof(keyboard_desc),.report_desc=keyboard_desc,.hs_Interval=1},
        {.bInEp=1,.InEpNum=2,.in_report_length=2,
         .report_desc_length=sizeof(consumer_desc),.report_desc=consumer_desc,.hs_Interval=1},
        {.bInEp=1,.bOutEp=1,.InEpNum=3,.OutEpNum=3,.in_report_length=64,.out_report_length=64,
         .report_desc_length=sizeof(vendor_desc),.report_desc=vendor_desc,.hs_Interval=1},
        {.bOutEp=1,.OutEpNum=4,.out_report_length=512,.feature_report_length=64,
         .report_desc_length=sizeof(isp_desc),.report_desc=isp_desc,.hs_Interval=4}
    }
};
static USB_DeviceDesc_t device_desc={18,1,0x0200,0,0,0,64,0x0c45,0x8037,0x0118,
                                   USBD_IDX_MFC_STR,USBD_IDX_PRODUCT_STR,USBD_IDX_SERIAL_STR,1};
static uint8_t language_desc[]={4,3,0x09,0x04},string_buffer[128];
static USB_DeviceDesc_t *get_device(USBD_Speed_t speed,uint16_t *length){
    (void)speed;*length=sizeof(device_desc);return &device_desc;
}
static uint8_t *get_language(USBD_Speed_t speed,uint16_t *length){
    (void)speed;*length=sizeof(language_desc);return language_desc;
}
static uint8_t *make_string(const char *text,uint16_t *length){
    USBD_GetString((uint8_t*)text,string_buffer,length);return string_buffer;
}
static uint8_t *get_manufacturer(USBD_Speed_t speed,uint16_t *length){
    (void)speed;return make_string("BAT68 Development",length);
}
static uint8_t *get_product(USBD_Speed_t speed,uint16_t *length){
#if BAT68_STANDALONE
    (void)speed;return make_string("BAT68 QMK",length);
#else
    (void)speed;return make_string("BAT68 Native USB Trial",length);
#endif
}
static uint8_t *get_serial(USBD_Speed_t speed,uint16_t *length){
#if BAT68_STANDALONE
    (void)speed;return make_string("B68QMK001",length);
#else
    (void)speed;return make_string("B68NATIVE001",length);
#endif
}
static uint8_t *get_configuration(USBD_Speed_t speed,uint16_t *length){
    (void)speed;return make_string("Keyboard and diagnostics",length);
}
static USBD_Descriptors_t descriptors={
    .bmAttributes=0,.bMaxPower=0xfa,.GetDeviceDescriptor=get_device,
    .GetLangIDStrDescriptor=get_language,.GetManufacturerStrDescriptor=get_manufacturer,
    .GetProductStrDescriptor=get_product,.GetSerialStrDescriptor=get_serial,
    .GetConfigurationStrDescriptor=get_configuration
};

static void usb_clocks(void){
    __HAL_USB_PHY_POR_ENABLE();__HAL_RCC_USBPHY12M_CLK_ENABLE();__HAL_RCC_USB_HS_CLK_ENABLE();
    __HAL_RCC_USBPHY_CLK_ENABLE();__HAL_RCC_USBPHY_CLK_DISABLE();
}
void HAL_PCD_MspInit(PCD_Handle_t *handle){
    (void)handle;usb_clocks();
    NVIC_ClearPendingIRQ(USB_HS_IRQn);NVIC_SetPriority(USB_HS_IRQn,1);NVIC_EnableIRQ(USB_HS_IRQn);
}
void USB_HS_IRQHandler(void){native_usb_irqs++;NATIVE_MAILBOX[4]=native_usb_irqs;HAL_PCD_IRQHandler();}

int native_usb_init(void){
    // Boot's valid-application path need not enable USB at all. Gate clocks
    // before the first USB register access, including the initial detach bit.
    usb_clocks();
    // Make the transition visible to the host before rebuilding USB state.
    SN_USB_HS->PHYTEST_b.UNPLUG=1;HAL_Delay(100);
    NATIVE_MAILBOX[11]=1;
    if(USBD_Init(&device,&descriptors)!=HAL_OK)return -1;
    NATIVE_MAILBOX[11]=2;
    if(USBD_RegisterClass(&device,&USBD_HID)!=HAL_OK)return -2;
    NATIVE_MAILBOX[11]=3;
    if(USBD_HID_RegisterReport(&reports)!=HAL_OK)return -3;
    NATIVE_MAILBOX[11]=4;
    if(USBD_ForceFS(&device,0)!=HAL_OK)return -4;
    NATIVE_MAILBOX[11]=5;
    if(USBD_Start(&device)!=HAL_OK)return -5;
    NATIVE_MAILBOX[11]=6;
    return 0;
}
static void put32(unsigned at,uint32_t value){
    for(unsigned i=0;i<4;i++)response[at+i]=(uint8_t)(value>>(8*i));
}
void native_usb_task(void){
    uint16_t led_length=0;
    uint8_t leds;
    if(USBD_HID_ReceiveReport(0,&leds,1,&led_length)==HAL_OK&&led_length==1)native_keyboard_leds=leds;
    if(response_pending){
        if(USBD_HID_SendReport(2,response,sizeof(response))==HAL_OK)response_pending=0;
        else return;
    }
    uint8_t packet[64];uint16_t length=0;
    if(USBD_HID_ReceiveReport(2,packet,sizeof(packet),&length)!=HAL_OK||length!=64)return;
    if(packet[0]!=0xaa||memcmp(packet+5,"B68",3))return;
    NATIVE_MAILBOX[14]++;
    memset(response,0,sizeof(response));response[0]=0x55;response[1]=packet[1];response[2]=32;
    memcpy(response+5,"B68",3);
#if BAT68_ENABLE_KEYBOARD
    if(native_keyboard_command(packet,response)){response_pending=1;return;}
#endif
    if(packet[1]!=0x7d&&packet[1]!=0x7e)return;
    if(packet[1]==0x7e){
#if BAT68_ENABLE_SCAN
        unsigned at=packet[3]|((unsigned)packet[4]<<8),count=packet[2];
        if(!count||count>24||at>=96||count>96-at)response[2]=0xff;
        else{
            uint32_t saved=__get_PRIMASK();__disable_irq();
            response[2]=count*2;response[3]=packet[3];response[4]=packet[4];
            for(unsigned i=0;i<count;i++){
                uint16_t value=native_raw[at+i];response[8+2*i]=value;response[9+2*i]=value>>8;
            }
            __set_PRIMASK(saved);
        }
#else
        response[2]=0xff;
#endif
        response_pending=1;return;
    }
    response[2]=48;memcpy(response+8,"B68N",4);
    response[12]=1;response[13]=1;response[14]=device.dev_speed;
#if BAT68_ENABLE_SCAN
    response[13]=2;response[15]=native_scan_phase;put32(28,native_scan_frames);
#endif
#if BAT68_ENABLE_KEYBOARD
    response[13]=3;
#endif
#if BAT68_STANDALONE
    response[13]=4;
#endif
    put32(16,native_usb_loops);put32(20,HAL_GetTick());put32(24,native_usb_irqs);
    memcpy(response+36,packet+8,4);
    put32(40,NATIVE_MAILBOX[3]);put32(44,NATIVE_MAILBOX[2]);
    put32(48,*(volatile const uint32_t*)0x7dffcu);
    response[52]=BAT68_STANDALONE;response[53]=BAT68_BRINGUP_GUARD;response_pending=1;
}
int native_usb_keyboard_send(const void *report){
    if(USBD_HID_SendReport(0,(uint8_t*)report,8)!=HAL_OK)return -1;
    memcpy(last_keyboard_report,report,8);return 0;
}
void native_usb_stop(void){USBD_Stop(&device);SN_USB_HS->PHYTEST_b.UNPLUG=1;}
int native_usb_reply_queued(void){return response_pending;}
