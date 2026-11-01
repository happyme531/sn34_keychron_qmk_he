// SPDX-License-Identifier: GPL-2.0-or-later
// Upstream QMK engine with source-built Hall, USB and persistent settings.
// There are no addresses or function calls into the original application.
#include "quantum.h"
#include "host_driver.h"
#include "keymap_introspection.h"
#include "keymap.generated.h"
#include "hall.generated.h"
#include "keymap_settings.h"
#include "native.h"
#include "sn34f28x_hal.h"
#include "sn34_flash.h"
#if BAT68_KEYCHRON_HE
#include "he.h"
#include "analog_matrix.h"
#endif

static uint16_t active_keymaps[2][MATRIX_ROWS][MATRIX_COLS];
static matrix_row_t matrix_state[MATRIX_ROWS];
static report_keyboard_t queued_report;
static uint8_t report_pending,owns_keyboard=1;
static uint32_t scans,last_frame;
uint16_t native_travel[128];

uint32_t timer_read32(void){return HAL_GetTick();}
uint16_t timer_read(void){return (uint16_t)HAL_GetTick();}
uint32_t timer_elapsed32(uint32_t last){return timer_read32()-last;}
uint16_t timer_elapsed(uint16_t last){return (uint16_t)(timer_read()-last);}
void wait_ms(unsigned n){HAL_Delay(n);}
void wait_us(unsigned n){for(volatile unsigned i=0;i<n*40u;i++)__asm__ volatile("nop");}
uint8_t keymap_layer_count(void){return 2;}
uint16_t keycode_at_keymap_location(uint8_t l,uint8_t r,uint8_t c){
    return l<2&&r<MATRIX_ROWS&&c<MATRIX_COLS?active_keymaps[l][r][c]:KC_TRNS;
}
#if !BAT68_KEYCHRON_HE
bool pre_process_record_quantum(keyrecord_t *record){(void)record;return true;}
#endif
static uint8_t keyboard_leds(void){return native_keyboard_leds;}
static void send_keyboard(report_keyboard_t *report){queued_report=*report;report_pending=1;}
static host_driver_t driver={.keyboard_leds=keyboard_leds,.send_keyboard=send_keyboard};
_Static_assert(sizeof(report_keyboard_t)==8,"Native keyboard uses eight-byte boot reports");

void native_keyboard_init(void){
    memcpy(active_keymaps,keymaps,sizeof(active_keymaps));
    qmk_settings_init(active_keymaps);host_set_driver(&driver);default_layer_set(1);
    report_pending=1;last_frame=native_scan_frames;
#if BAT68_KEYCHRON_HE
    bat68_he_init();
#endif
}
static void key_event(unsigned slot,bool pressed){action_exec(MAKE_KEYEVENT(slot/16,slot%16,pressed));}

void native_keyboard_task(void){
    if(last_frame!=native_scan_frames){
        uint16_t raw[96];
        uint32_t saved=__get_PRIMASK();__disable_irq();
        for(unsigned i=0;i<96;i++)raw[i]=native_raw[i];
        last_frame=native_scan_frames;__set_PRIMASK(saved);
        matrix_row_t next[MATRIX_ROWS]={0};
#if BAT68_KEYCHRON_HE
        bat68_he_scan(raw,next);
        for(unsigned i=0;i<BAT68_HALL_KEYS;i++){
            const bat68_hall_key_t *key=&hall_keys[i];
            native_travel[key->electrical]=analog_matrix_get_travel(key->slot/16,key->slot%16)*330u/240u;
        }
#else
        for(unsigned i=0;i<BAT68_HALL_KEYS;i++){
            const bat68_hall_key_t *key=&hall_keys[i];
            unsigned travel=0;
            // Normalized travel units, not millimetres: the released reference
            // is measured per key; bottom is the initial factory ADC estimate.
            if(raw[key->slot]<key->idle){
                travel=(key->idle-raw[key->slot])*330u/(key->idle-key->bottom);
                if(travel>330)travel=330;
            }
            native_travel[key->electrical]=(uint16_t)travel;
            bool previous=(matrix_state[key->slot/16]>>(key->slot%16))&1;
            if(travel>=(previous?BAT68_RELEASE:BAT68_ACTUATION))next[key->slot/16]|=1u<<(key->slot%16);
        }
#endif
        const unsigned fn=90;
        bool old_fn=(matrix_state[fn/16]>>(fn%16))&1,new_fn=(next[fn/16]>>(fn%16))&1;
        if(new_fn&&!old_fn)key_event(fn,true);
        for(unsigned slot=0;slot<96;slot++){
            if(slot==fn)continue;
            bool old=(matrix_state[slot/16]>>(slot%16))&1,now=(next[slot/16]>>(slot%16))&1;
            if(old!=now)key_event(slot,now);
        }
        if(old_fn&&!new_fn)key_event(fn,false);
        memcpy(matrix_state,next,sizeof(next));action_exec(MAKE_TICK_EVENT);scans++;
    }
    if(report_pending&&native_usb_keyboard_send(&queued_report)==0)report_pending=0;
}
static void put16(uint8_t *p,unsigned value){p[0]=value;p[1]=value>>8;}
static void put32(uint8_t *p,uint32_t value){put16(p,value);put16(p+2,value>>16);}
static int released(void){unsigned any=0;for(unsigned i=0;i<MATRIX_ROWS;i++)any|=matrix_state[i];return !any;}

int native_keyboard_command(const uint8_t *rx,uint8_t *tx){
    unsigned cmd=rx[1],count=rx[2],r=rx[3],c=rx[4],offset=r|(c<<8);
    unsigned value=rx[8]|((unsigned)rx[9]<<8);
    uint32_t signature=value|((uint32_t)rx[10]<<16)|((uint32_t)rx[11]<<24);
    tx[2]=0xff;
#if BAT68_KEYCHRON_HE
    if(bat68_he_command(rx,tx,released()))return 1;
#endif
    if(cmd==0x70){
        tx[2]=24;memcpy(tx+8,"B68P",4);tx[12]=2;tx[13]=96;tx[14]=128;tx[15]=48;
        put16(tx+16,0x0118);put16(tx+18,8192);
    }else if(cmd==0x71||cmd==0x77){
        unsigned size=cmd==0x71?96:128;
        if(count&&count<=24&&offset<size&&count<=size-offset){
            uint32_t saved=__get_PRIMASK();__disable_irq();
            for(unsigned i=0;i<count;i++)put16(tx+8+2*i,cmd==0x71?native_raw[offset+i]:native_travel[offset+i]);
            __set_PRIMASK(saved);tx[2]=count*2;put16(tx+3,offset);
        }
    }else if(cmd==0x72||cmd==0x73){
        uint32_t limit=8192,base=0x00200000u;
        if(cmd==0x73){offset=signature;limit=0x7e000u;base=0;}
        if(count&&count<=48&&offset<limit&&count<=limit-offset){
            memcpy(tx+8,(const void*)(base+offset),count);tx[2]=count;
            if(cmd==0x73)put32(tx+56,offset);else put16(tx+3,offset);
        }
    }else if(cmd==0x74){
        tx[2]=56;memcpy(tx+8,"B68Q",4);tx[12]=BAT68_KEYCHRON_HE?7:BAT68_STANDALONE?6:5;tx[13]=2;tx[14]=MATRIX_ROWS;tx[15]=MATRIX_COLS;
        tx[16]=layer_state;tx[17]=1;tx[18]=report_pending;tx[19]=owns_keyboard;
        put16(tx+20,BAT68_ACTUATION);put16(tx+22,BAT68_RELEASE);
        for(unsigned i=0;i<MATRIX_ROWS;i++)put16(tx+24+2*i,matrix_state[i]);
        put32(tx+36,scans);memcpy(tx+40,&queued_report,8);put32(tx+48,qmk_settings_sequence());
        tx[52]=qmk_settings_slot();tx[53]=qmk_settings_dirty();tx[54]=1;tx[55]=1;
        put16(tx+56,0x19|(BAT68_STANDALONE?0x40:0)|(BAT68_BRINGUP_GUARD?0x20:0)|(BAT68_KEYCHRON_HE?0x80:0));
    }else if(cmd==0x75||cmd==0x76){
        if(count<2&&r<MATRIX_ROWS&&c<MATRIX_COLS){
            if(cmd==0x75){
                if(matrix_state[r]&(1u<<c))return 1;
                if(active_keymaps[count][r][c]!=value){active_keymaps[count][r][c]=value;qmk_settings_changed();}
            }
            tx[2]=2;tx[3]=r;tx[4]=c;put16(tx+8,active_keymaps[count][r][c]);
        }
    }else if(cmd==0x79){
        if(released()&&signature==0x45564153u){
            int result=qmk_settings_save(active_keymaps);
            if(result>=0){tx[2]=16;tx[8]=result;tx[9]=qmk_settings_slot();put32(tx+12,qmk_settings_sequence());}
        }
    }else if(cmd==0x7a){
        if(released()&&signature==0x54424552u){native_restart_requested=1;tx[2]=1;tx[8]=1;}
    }else if(cmd==0x7b){
#if BAT68_BRINGUP_GUARD
        if(released()&&signature==0x21544d43u){
            uint32_t saved=__get_PRIMASK();__disable_irq();
            int result=sn34_flash_validate_application();__set_PRIMASK(saved);
            if(!result){tx[2]=1;tx[8]=1;}
        }
#endif
    }else if(cmd==0x78){
        // Running the native image requires its QMK engine to own key reports.
        if(count==1&&released()){tx[2]=1;tx[8]=1;}
    }else return 0;
    return 1;
}
