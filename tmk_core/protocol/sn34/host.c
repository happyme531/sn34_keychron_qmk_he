// SPDX-License-Identifier: GPL-2.0-or-later
// FIFO preserves press/release sequences produced within one QMK iteration.
#include "quantum.h"
#include "platform.h"
#include "native.h"
#include "raw_hid.h"
#include "sn34f28x_hal.h"
#include "game_controller_common.h"
enum { QUEUE_COUNT=256,REPORT_MAX=64,LOOP_HEADROOM=96 };
typedef struct {uint8_t interface,length;uint8_t data[REPORT_MAX];} queued_t;
static queued_t queue[QUEUE_COUNT];
enum { NO_REPORT=QUEUE_COUNT,INTERFACES=6 };
static uint16_t next[QUEUE_COUNT],first[INTERFACES],last[INTERFACES],free_head,count;
static bool connected;
static bool recover;
uint32_t sn34_report_overflows;
uint32_t sn34_queue_peak,sn34_axis_coalesced;
static void reset_queue(void){
    for(unsigned i=0;i<QUEUE_COUNT;i++)next[i]=i+1;
    for(unsigned i=0;i<INTERFACES;i++)first[i]=last[i]=NO_REPORT;
    free_head=count=0;
}
void sn34_host_task(void){
    if(!sn34_usb_configured()){
        reset_queue();connected=false;recover=false;return;
    }
    if(!connected){connected=true;clear_keyboard();game_controller_clear();}
    // A stalled configuration or XInput endpoint must not hold up typing.
    // Preserve order within each interface, while servicing independent FIFOs.
    for(unsigned interface=0;interface<INTERFACES;interface++)while(first[interface]!=NO_REPORT){
        unsigned index=first[interface];queued_t *q=&queue[index];
        if(sn34_usb_send(interface,q->data,q->length))break;
        first[interface]=next[index];if(first[interface]==NO_REPORT)last[interface]=NO_REPORT;
        next[index]=free_head;free_head=index;count--;
    }
    // A host that stops polling can exhaust even a bounded FIFO. Once it
    // recovers, neutralize every report rather than leave a lost release held.
    if(recover){recover=false;clear_keyboard();game_controller_clear();}
}
static void send_report(unsigned interface,const void *data,unsigned length){
    if(interface>=INTERFACES || length>REPORT_MAX)return;
    if(!sn34_usb_configured()){reset_queue();connected=false;return;}
    const uint8_t *bytes=data;
    bool axis=interface==SN34_USB_XINPUT || (interface==SN34_USB_SHARED && length==11 && bytes[0]==7);
    if(axis && last[interface]!=NO_REPORT){
        queued_t *previous=&queue[last[interface]];
        unsigned offset=interface==SN34_USB_XINPUT?2:7,buttons=interface==SN34_USB_XINPUT?2:4;
        if(previous->length==length && (interface==SN34_USB_XINPUT || previous->data[0]==7) &&
           !memcmp(previous->data+offset,bytes+offset,buttons)){
            memcpy(previous->data,bytes,length);sn34_axis_coalesced++;sn34_host_task();return;
        }
    }
    bool background=axis || interface==SN34_USB_RAW || interface==SN34_USB_DIAGNOSTIC;
    unsigned limit=background?QUEUE_COUNT-LOOP_HEADROOM:QUEUE_COUNT;
    if(count>=limit){
        if(background){sn34_report_overflows++;return;}
        uint32_t start=HAL_GetTick();
        do{sn34_host_task();}while(count==QUEUE_COUNT && HAL_GetTick()-start<100);
        if(count==QUEUE_COUNT){sn34_report_overflows++;recover=true;return;}
    }
    unsigned index=free_head;free_head=next[index];next[index]=NO_REPORT;
    queue[index].interface=interface;queue[index].length=length;memcpy(queue[index].data,data,length);
    if(last[interface]==NO_REPORT)first[interface]=index;else next[last[interface]]=index;
    last[interface]=index;count++;if(count>sn34_queue_peak)sn34_queue_peak=count;
    sn34_host_task();
}
bool sn34_host_ready(void){return sn34_usb_configured() && count<=QUEUE_COUNT-LOOP_HEADROOM;}
unsigned sn34_host_queued(void){return count;}
static uint8_t leds(void){return native_keyboard_leds;}
static void keyboard(report_keyboard_t *r){sn34_usb_set_last_boot(r);send_report(SN34_USB_BOOT,r,sizeof(*r));}
static void nkro(report_nkro_t *r){send_report(SN34_USB_SHARED,r,sizeof(*r));}
static void mouse(report_mouse_t *r){send_report(SN34_USB_SHARED,r,sizeof(*r));}
static void extra(report_extra_t *r){send_report(SN34_USB_SHARED,r,sizeof(*r));}
static void joystick(report_joystick_t *r){send_report(SN34_USB_SHARED,r,sizeof(*r));}
static void xinput(report_xinput_t *r){send_report(SN34_USB_XINPUT,r,sizeof(*r));}
static void raw_send(uint8_t *data,uint8_t length){if(length==RAW_EPSIZE)send_report(SN34_USB_RAW,data,length);}
host_driver_t sn34_host_driver={.keyboard_leds=leds,.send_keyboard=keyboard,.send_nkro=nkro,
    .send_mouse=mouse,.send_extra=extra,.send_joystick=joystick,.send_xinput=xinput,.send_raw_hid=raw_send};
void sn34_host_init(void){reset_queue();host_set_driver(&sn34_host_driver);}
