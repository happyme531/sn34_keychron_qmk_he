// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "host_driver.h"
#include "keymap_introspection.h"
#include "keymap.generated.h"
#include "keymap_settings.h"
#include "diagnostics.h"
#include "native_trial.generated.h"

extern uint8_t __data_load[],__data_start[],__data_end[],__bss_start[],__bss_end[];
static uint16_t active_keymaps[2][MATRIX_ROWS][MATRIX_COLS];
static matrix_row_t matrix_state[MATRIX_ROWS];
static report_keyboard_t queued_report;
static uint8_t report_pending;
static uint32_t initialized;
static uint32_t scans;
static volatile uint8_t owns_keyboard;
static uint8_t reboot_pending;
static uint32_t reboot_requested_at;

#define RX ((volatile uint8_t*)0x20003668)
#define TX ((volatile uint8_t*)0x20003628)
#define PENDING (*(volatile uint8_t*)0x20000365)
#define READY (*(volatile uint8_t*)0x20000364)
#define TRAVEL ((volatile uint16_t*)0x200040d8)
#define LOOKUP ((const uint8_t*)0x14fe4)

uint32_t timer_read32(void){return *(volatile uint32_t*)0x20000580;}
uint16_t timer_read(void){return (uint16_t)timer_read32();}
uint32_t timer_elapsed32(uint32_t last){return timer_read32()-last;}
uint16_t timer_elapsed(uint16_t last){return (uint16_t)(timer_read()-last);}
void wait_ms(unsigned n){uint32_t start=timer_read32();while(timer_read32()-start<n){}}
void wait_us(unsigned n){for(volatile unsigned i=0;i<n*40;i++)__asm__ volatile("nop");}
uint8_t keymap_layer_count(void){return 2;}
uint16_t keycode_at_keymap_location(uint8_t l,uint8_t r,uint8_t c){
    return l<2&&r<MATRIX_ROWS&&c<MATRIX_COLS?active_keymaps[l][r][c]:KC_TRNS;
}
bool pre_process_record_quantum(keyrecord_t *record){(void)record;return true;}
static uint8_t keyboard_leds(void){return *(volatile uint8_t*)0x200035d0;}
static void send_keyboard(report_keyboard_t *report){queued_report=*report;report_pending=1;}
static host_driver_t driver={.keyboard_leds=keyboard_leds,.send_keyboard=send_keyboard};
_Static_assert(sizeof(report_keyboard_t)==8,"Stock boot keyboard uses eight bytes");

void qmk_bridge_init(void){
    for(uint8_t *p=__data_start,*s=__data_load;p<__data_end;) *p++=*s++;
    for(uint8_t *p=__bss_start;p<__bss_end;) *p++=0;
    memcpy(active_keymaps,keymaps,sizeof(active_keymaps));
    qmk_settings_init(active_keymaps);
    host_set_driver(&driver);
    default_layer_set(1);
    owns_keyboard=BAT68_DEFAULT_QMK;
    report_pending=1;
    initialized=0x514d4b31;
}

static void key_event(unsigned slot,bool pressed){
    action_exec(MAKE_KEYEVENT(slot/16,slot%16,pressed));
}

void qmk_bridge_task(void){
    if(initialized!=0x514d4b31)return;
    if(reboot_pending&&timer_elapsed32(reboot_requested_at)>=50){
#if BAT68_NATIVE_TRIAL_ENTRY
        if(reboot_pending==2){
            ((void(*)(void))BAT68_NATIVE_TRIAL_ENTRY)();
            for(;;)__asm__ volatile("nop");
        }
#endif
        __asm__ volatile("dsb":::"memory");
        *(volatile uint32_t*)0xe000ed0c=0x05fa0004;
        __asm__ volatile("dsb":::"memory");
        for(;;)__asm__ volatile("nop");
    }
    matrix_row_t next[MATRIX_ROWS]={0};
    uint32_t saved;
    __asm__ volatile("mrs %0,primask\n cpsid i":"=r"(saved)::"memory");
    for(unsigned e=0;e<128;e++){
        unsigned group=e&7,slot=e>>3;
        if(group>=6||LOOKUP[e]==0x7d)continue;
        bool previous=(matrix_state[group]>>slot)&1;
        if(TRAVEL[e]>=(previous?BAT68_RELEASE:BAT68_ACTUATION))next[group]|=1u<<slot;
    }
    __asm__ volatile("msr primask,%0"::"r"(saved):"memory");
    const unsigned fn=90;
    bool old_fn=(matrix_state[fn/16]>>(fn%16))&1,new_fn=(next[fn/16]>>(fn%16))&1;
    if(new_fn&&!old_fn)key_event(fn,true);
    for(unsigned slot=0;slot<96;slot++){
        if(slot==fn)continue;
        bool old=(matrix_state[slot/16]>>(slot%16))&1,now=(next[slot/16]>>(slot%16))&1;
        if(old!=now)key_event(slot,now);
    }
    if(old_fn&&!new_fn)key_event(fn,false);
    memcpy(matrix_state,next,sizeof(next));
    action_exec(MAKE_TICK_EVENT);
    if(report_pending&&owns_keyboard){
        typedef int (*stock_send_t)(int,const void*,unsigned);
        if(((stock_send_t)0x10905)(0,&queued_report,8)==0)report_pending=0;
    }
    scans++;
}

int qmk_keyboard_owned(void){return initialized==0x514d4b31&&owns_keyboard;}

static void put16(unsigned p,unsigned n){TX[p]=(uint8_t)n;TX[p+1]=(uint8_t)(n>>8);}
int qmk_bridge_command(void){
    if(!PENDING||RX[0]!=0xaa||RX[5]!='B'||RX[6]!='6'||RX[7]!='8'||RX[1]<0x74||RX[1]>0x7c)return 0;
    unsigned cmd=RX[1],count=RX[2],r=RX[3],c=RX[4];
    unsigned value=RX[8]|((unsigned)RX[9]<<8),offset=r|(c<<8);
    uint32_t signature=RX[8]|((uint32_t)RX[9]<<8)|((uint32_t)RX[10]<<16)|((uint32_t)RX[11]<<24);
    PENDING=0;for(unsigned i=0;i<64;i++)TX[i]=0;
    TX[0]=0x55;TX[1]=(uint8_t)cmd;TX[5]='B';TX[6]='6';TX[7]='8';
    if(cmd==0x74){
        TX[2]=56;TX[8]='B';TX[9]='6';TX[10]='8';TX[11]='Q';
        TX[12]=BAT68_NATIVE_TRIAL_ENTRY?4:3;TX[13]=2;TX[14]=MATRIX_ROWS;TX[15]=MATRIX_COLS;TX[16]=(uint8_t)layer_state;
        TX[17]=(initialized==0x514d4b31);TX[18]=report_pending;
        TX[19]=owns_keyboard;
        put16(20,BAT68_ACTUATION);put16(22,BAT68_RELEASE);
        for(unsigned i=0;i<MATRIX_ROWS;i++)put16(24+2*i,matrix_state[i]);
        put16(36,scans);put16(38,scans>>16);
        for(unsigned i=0;i<8;i++)TX[40+i]=((uint8_t*)&queued_report)[i];
        put16(48,qmk_settings_sequence());put16(50,qmk_settings_sequence()>>16);
        TX[52]=qmk_settings_slot();TX[53]=qmk_settings_dirty();TX[54]=BAT68_DEFAULT_QMK;TX[55]=1;
        put16(56,3|(BAT68_NATIVE_TRIAL_ENTRY?4:0));put16(58,bat68_snapshot_words());put16(60,BAT68_NATIVE_TRIAL_BYTES);
    }else if(cmd==0x75||cmd==0x76){
        if(count>=2||r>=MATRIX_ROWS||c>=MATRIX_COLS)TX[2]=0xff;
        else{
            if(cmd==0x75){
                if(matrix_state[r]&(1u<<c)){TX[2]=0xff;READY=1;return 1;}
                if(active_keymaps[count][r][c]!=(uint16_t)value){
                    active_keymaps[count][r][c]=(uint16_t)value;qmk_settings_changed();
                }
            }
            TX[2]=2;TX[3]=(uint8_t)r;TX[4]=(uint8_t)c;put16(8,active_keymaps[count][r][c]);
        }
    }else if(cmd==0x78||cmd==0x79||cmd==0x7a||cmd==0x7c){
        unsigned any=0;for(unsigned i=0;i<MATRIX_ROWS;i++)any|=matrix_state[i];
        if(any)TX[2]=0xff;
        else if(cmd==0x79){
            if(signature!=0x45564153u){TX[2]=0xff;READY=1;return 1;}
            int result=qmk_settings_save(active_keymaps);
            if(result<0)TX[2]=0xff;
            else{
                TX[2]=16;TX[8]=(uint8_t)result;TX[9]=qmk_settings_slot();
                put16(12,qmk_settings_sequence());put16(14,qmk_settings_sequence()>>16);
            }
        }else if(cmd==0x7a){
            if(signature!=0x54424552u)TX[2]=0xff;
            else{reboot_pending=1;reboot_requested_at=timer_read32();TX[2]=1;TX[8]=1;}
        }else if(cmd==0x7c){
            if(!BAT68_NATIVE_TRIAL_ENTRY||signature!=0x4253554eu)TX[2]=0xff;
            else{reboot_pending=2;reboot_requested_at=timer_read32();TX[2]=1;TX[8]=1;}
        }else if(count>1)TX[2]=0xff;
        else{
            owns_keyboard=(uint8_t)count;
            memset(&queued_report,0,sizeof(queued_report));report_pending=1;
            *(volatile uint8_t*)0x2000040b=1;
            TX[2]=1;TX[8]=owns_keyboard;
        }
    }else if(cmd==0x7b){
        if(!count||count>12||offset>=bat68_snapshot_words()||count>bat68_snapshot_words()-offset)TX[2]=0xff;
        else{
            TX[2]=(uint8_t)(count*4);put16(3,offset);
            uint32_t saved;__asm__ volatile("mrs %0,primask\n cpsid i":"=r"(saved)::"memory");
            for(unsigned i=0;i<count;i++){
                uint32_t word=0;bat68_snapshot_word(offset+i,&word);
                put16(8+i*4,word);put16(10+i*4,word>>16);
            }
            __asm__ volatile("msr primask,%0"::"r"(saved):"memory");
        }
    }else{
        if(!count||count>24||offset>=128||count>128-offset)TX[2]=0xff;
        else{TX[2]=(uint8_t)(2*count);put16(3,offset);for(unsigned i=0;i<count;i++)put16(8+2*i,TRAVEL[offset+i]);}
    }
    READY=1;return 1;
}
