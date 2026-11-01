// SPDX-License-Identifier: GPL-2.0-or-later
#include "Middleware_USBD.h"
#include "usbd_core.h"
#include "platform.h"
#include "native.h"
#include "mailbox.h"
#include "usb_device_state.h"
#include "xinput_usb.h"
#include "progmem.h"
#include "rgb_matrix.h"
#define CONCAT(a,b) a##b
#define CONCAT_EXPANDED(a,b) CONCAT(a,b)
#include "reports.generated.h"
#include <string.h>
static USBD_Handle_t device __attribute__((aligned(4)));
volatile uint32_t native_usb_irqs;
volatile uint32_t native_usb_irq_cycles;
uint8_t native_keyboard_leds;
static uint8_t last_boot[8] __attribute__((aligned(4))),last_shared[10][64] __attribute__((aligned(4))),shared_length[10];
static uint8_t response[64] __attribute__((aligned(4))),response_pending;
static uint8_t previous_state=255;
static uint32_t enumeration_started,detached_at,device_descriptor_reads;
static uint8_t enumeration_phase,enumerated_once;
static int8_t enumeration_error;
static const uint8_t diagnostic_report[] __attribute__((aligned(4)))={0x06,0x68,0xff,0x09,0x61,0xa1,1,0x09,0x62,0x15,0,0x26,0xff,0,
    0x75,8,0x95,64,0x81,2,0x09,0x63,0x95,64,0x91,2,0xc0};
// Application OTA only needs the entry Feature report. Programming data goes
// to the retained Bootloader after reboot. Its unused interrupt OUT endpoint
// would consume a ninth FIFO on a controller that physically provides eight.
static const uint8_t ota_report[] __attribute__((aligned(4)))={0x06,0x67,0xff,0x09,0x61,0xa1,1,0x09,0x62,0x15,0,0x26,0xff,0,
    0x75,8,0x95,64,0xb1,2,0xc0};
static HAL_Status_T get_input(uint8_t idx,uint8_t id,uint8_t *data,uint16_t *length){
    if(idx==BAT68_USB_BOOT && !id){memcpy(data,last_boot,8);*length=8;return HAL_OK;}
    if(idx==BAT68_USB_SHARED && id<10 && shared_length[id]){
        *length=shared_length[id];memcpy(data,last_shared[id],*length);return HAL_OK;
    }
    return HAL_ERROR;
}
static HAL_Status_T set_feature(uint8_t idx,uint8_t id,uint8_t *data,uint16_t length){
    static const uint8_t magic[]={0xaa,0x55,0xa5,0x5a,0xff,0,0x33,0xcc};
    if(idx!=BAT68_USB_OTA || id || length<8 || memcmp(data,magic,8))return HAL_ERROR;
    native_boot_requested=1;return HAL_OK;
}
static USBD_ReportInfo_t reports={.intf_num=5,.GetInputReport_isr_cb=get_input,.SetFeatureReport_isr_cb=set_feature,
    .intf_param={
        {.subclass=1,.protocol=1,.bInEp=1,.InEpNum=1,.in_report_length=8,.out_report_length=1,
         .report_desc_length=sizeof(KeyboardReport),.report_desc=(uint8_t*)KeyboardReport,.hs_Interval=1},
        {.bInEp=1,.InEpNum=2,.in_report_length=64,.out_report_length=2,
         .report_desc_length=sizeof(SharedReport),.report_desc=(uint8_t*)SharedReport,.hs_Interval=1},
        {.bInEp=1,.bOutEp=1,.InEpNum=3,.OutEpNum=3,.in_report_length=64,.out_report_length=64,
         .report_desc_length=sizeof(diagnostic_report),.report_desc=(uint8_t*)diagnostic_report,.hs_Interval=1},
        {.feature_report_length=64,
         .report_desc_length=sizeof(ota_report),.report_desc=(uint8_t*)ota_report},
        {.bInEp=1,.bOutEp=1,.InEpNum=5,.OutEpNum=5,.in_report_length=32,.out_report_length=32,
         .report_desc_length=sizeof(RawReport),.report_desc=(uint8_t*)RawReport,.hs_Interval=1}}};
static USB_DeviceDesc_t device_desc __attribute__((aligned(4)))={18,1,0x0200,0,0,0,64,VENDOR_ID,PRODUCT_ID,DEVICE_VER,
    USBD_IDX_MFC_STR,USBD_IDX_PRODUCT_STR,USBD_IDX_SERIAL_STR,1};
static uint8_t language_desc[] __attribute__((aligned(4)))={4,3,0x09,0x04},string_buffer[128] __attribute__((aligned(4)));
static USB_DeviceDesc_t *get_device(USBD_Speed_t s,uint16_t *n){(void)s;device_descriptor_reads++;*n=sizeof(device_desc);return &device_desc;}
static uint8_t *get_language(USBD_Speed_t s,uint16_t *n){(void)s;*n=sizeof(language_desc);return language_desc;}
static uint8_t *string(const char *text,uint16_t *n){USBD_GetString((uint8_t*)text,string_buffer,n);return string_buffer;}
static uint8_t *manufacturer(USBD_Speed_t s,uint16_t *n){(void)s;return string("BAT68 Open Firmware",n);}
static uint8_t *product(USBD_Speed_t s,uint16_t *n){(void)s;return string("BAT68 QMK HE",n);}
static uint8_t *serial(USBD_Speed_t s,uint16_t *n){(void)s;return string("B68QMK002",n);}
static uint8_t *configuration(USBD_Speed_t s,uint16_t *n){(void)s;return string("QMK keyboard, gamepad and configuration",n);}
static USBD_Descriptors_t descriptors={.bmAttributes=0,.bMaxPower=0xfa,.GetDeviceDescriptor=get_device,
    .GetLangIDStrDescriptor=get_language,.GetManufacturerStrDescriptor=manufacturer,.GetProductStrDescriptor=product,
    .GetSerialStrDescriptor=serial,.GetConfigurationStrDescriptor=configuration};
static void clocks(void){
    __HAL_USB_PHY_POR_ENABLE();__HAL_RCC_USBPHY12M_CLK_ENABLE();__HAL_RCC_USB_HS_CLK_ENABLE();
    __HAL_RCC_USBPHY_CLK_ENABLE();__HAL_RCC_USBPHY_CLK_DISABLE();
}
void HAL_PCD_MspInit(PCD_Handle_t *h){(void)h;clocks();NVIC_DisableIRQ(USB_HS_IRQn);NVIC_ClearPendingIRQ(USB_HS_IRQn);NVIC_SetPriority(USB_HS_IRQn,1);}
void USB_HS_IRQHandler(void){
    uint32_t started=DWT->CYCCNT;
    native_usb_irqs++;NATIVE_MAILBOX[4]=native_usb_irqs;HAL_PCD_IRQHandler();
    native_usb_irq_cycles+=DWT->CYCCNT-started;
}
int native_usb_init(void){
    clocks();SN_USB_HS->PHYTEST_b.UNPLUG=1;HAL_Delay(100);usb_device_state_init();
    if(USBD_Init(&device,&descriptors)!=HAL_OK)return -1;
    if(USBD_RegisterClass(&device,&USBD_HID)!=HAL_OK)return -2;
    if(USBD_HID_RegisterReport(&reports)!=HAL_OK)return -3;
    uint16_t hid_length=0;
    // The SDK allocates HID interface IDs lazily when constructing its class
    // descriptor. Reserve 0..4 before the independent XUSB class requests 5.
    if(!USBD_HID.GetClassDescriptor(&USBD_HID,USBD_SPEED_HIGH,&hid_length) || !hid_length)return -7;
    if(USBD_RegisterClass(&device,&bat68_xinput_class)!=HAL_OK)return -6;
    USBD_RegisterVndCallabck(&device,bat68_xinput_vendor,NULL);
    if(USBD_ForceFS(&device,0)!=HAL_OK)return -4;
    enumeration_started=HAL_GetTick();enumeration_phase=enumerated_once=0;enumeration_error=0;
    // Class registration and interface allocation must finish before an IRQ
    // can process a host request. The PHY stays detached until USBD_Start.
    NVIC_ClearPendingIRQ(USB_HS_IRQn);NVIC_EnableIRQ(USB_HS_IRQn);
    return USBD_Start(&device)==HAL_OK?0:-5;
}
static bool enumeration_recovery(void){
    if(bat68_usb_configured())enumerated_once=1;
    uint32_t now=HAL_GetTick();
    if(!enumerated_once && !bat68_usb_suspended() && enumeration_phase==0 && (uint32_t)(now-enumeration_started)>=5000u){
        // Retry only a failed initial enumeration, never an established link
        // or a sleeping host. A bounded FS attempt avoids repeated reconnects.
        NVIC_DisableIRQ(USB_HS_IRQn);
        // SET_CONFIGURATION or suspend may have arrived since the first
        // state check. Recheck while the USB IRQ is masked before detaching.
        if(bat68_usb_configured() || bat68_usb_suspended()){
            if(bat68_usb_configured())enumerated_once=1;
            NVIC_EnableIRQ(USB_HS_IRQn);return false;
        }
        if(USBD_Stop(&device)!=HAL_OK){enumeration_error=-1;enumeration_phase=3;return true;}
        detached_at=now;enumeration_phase=1;
    }
    if(enumeration_phase==1){
        if((uint32_t)(now-detached_at)<300u)return true;
        if(USBD_Reset(&device)!=HAL_OK || USBD_ForceFS(&device,1)!=HAL_OK){enumeration_error=-2;enumeration_phase=3;return true;}
        device.dev_speed=USBD_SPEED_FULL;
        NVIC_ClearPendingIRQ(USB_HS_IRQn);NVIC_EnableIRQ(USB_HS_IRQn);
        if(USBD_Start(&device)!=HAL_OK){enumeration_error=-3;enumeration_phase=3;return true;}
        enumeration_phase=2;
    }
    return enumeration_phase==3;
}
void bat68_usb_diagnostics(uint8_t out[24]){
    memset(out,0,24);out[0]=1;out[1]=device.dev_state;out[2]=device.dev_speed;
    out[3]=enumeration_phase;out[4]=enumerated_once;out[5]=(uint8_t)enumeration_error;
    uint32_t values[]={device_descriptor_reads,native_usb_irqs,HAL_GetTick()-enumeration_started,detached_at};
    memcpy(out+8,values,sizeof(values));
}
bool bat68_usb_configured(void){return device.dev_state==USBD_STATE_CONFIGURED;}
bool bat68_usb_suspended(void){return device.dev_state==USBD_STATE_SUSPENDED || device.dev_state==USBD_STATE_SLEEP;}
bool bat68_usb_boot_protocol(void){return USBD_HID_ReceiveProtocol(BAT68_USB_BOOT)==0;}
void bat68_usb_set_last_boot(const void *data){memcpy(last_boot,data,8);}
int bat68_usb_send(unsigned interface,const void *data,unsigned length){
    if(interface==BAT68_USB_XINPUT)return bat68_xinput_send(data,length);
    if(interface>=5 || length>64)return -1;
    if(USBD_HID_SendReport(interface,(uint8_t*)data,length)!=HAL_OK)return -1;
    if(interface==BAT68_USB_SHARED && length && *(const uint8_t*)data<10){
        unsigned id=*(const uint8_t*)data;memcpy(last_shared[id],data,length);shared_length[id]=length;
    }
    return 0;
}
int bat68_usb_receive(unsigned interface,void *data,unsigned size){
    uint16_t length=0;
    return USBD_HID_ReceiveReport(interface,data,size,&length)==HAL_OK?(int)length:0;
}
void native_usb_task(void){
    if(enumeration_recovery())return;
    uint8_t leds[2],packet[64];int length;
    if(bat68_usb_receive(0,leds,1)==1)native_keyboard_leds=leds[0];
    if((length=bat68_usb_receive(1,leds,2))>0)native_keyboard_leds=leds[length-1];
    if(previous_state!=device.dev_state){
        bool was_suspended=previous_state==USBD_STATE_SUSPENDED || previous_state==USBD_STATE_SLEEP;
        previous_state=device.dev_state;
        bool suspended=bat68_usb_suspended();
        rgb_matrix_set_suspend_state(suspended);
        if(suspended)usb_device_state_set_suspend(device.CurrentConfigValue!=0,device.CurrentConfigValue);
        else if(was_suspended)usb_device_state_set_resume(bat68_usb_configured(),device.CurrentConfigValue);
        else usb_device_state_set_configuration(bat68_usb_configured(),device.CurrentConfigValue);
    }
    usb_hid_protocol_t protocol=bat68_usb_boot_protocol()?USB_PROTOCOL_BOOT:USB_PROTOCOL_REPORT;
    if(usb_device_state_get_protocol()!=protocol)usb_device_state_set_protocol(protocol);
    if(usb_device_state_get_leds()!=native_keyboard_leds)usb_device_state_set_leds(native_keyboard_leds);
    if(response_pending && !bat68_usb_send(2,response,64))response_pending=0;
    if(!response_pending && bat68_usb_receive(2,packet,64)==64 && packet[0]==0xaa && !memcmp(packet+5,"B68",3)){
        memset(response,0,64);response[0]=0x55;response[1]=packet[1];memcpy(response+5,"B68",3);
        bat68_diagnostic(packet,response);response_pending=1;
    }
}
void raw_hid_task(void){
    uint8_t packet[32];if(bat68_usb_receive(4,packet,32)==32)bat68_raw_hid_receive(packet,32);
}
int native_usb_reply_queued(void){return response_pending;}
