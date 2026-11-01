// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "platform.h"
#include "native.h"
#include "analog_matrix.h"
#include "dynamic_keymap.h"
#include "board.generated.h"
#include "sn34f28x_hal.h"
#include "perf.h"
static void put16(uint8_t *p,unsigned v){p[0]=v;p[1]=v>>8;}
static void put32(uint8_t *p,uint32_t v){put16(p,v);put16(p+2,v>>16);}
int bat68_diagnostic(const uint8_t *rx,uint8_t *tx){
    unsigned cmd=rx[1],n=rx[2],r=rx[3],c=rx[4],at=r|(c<<8);
    uint32_t value;memcpy(&value,rx+8,4);tx[2]=255;
    if(cmd==0x70){tx[2]=24;memcpy(tx+8,"B68P",4);tx[12]=2;tx[13]=96;tx[14]=128;tx[15]=48;put16(tx+16,DEVICE_VER);put16(tx+18,BAT68_BOOT_USER_OFFSET);}
    else if(cmd==0x71 && n && n<=24 && at+n<=96){
        const uint16_t *samples;uint32_t frame=native_scan_frames-1u;
        if(native_scan_acquire(&samples,&frame)){
            tx[2]=n*2;put16(tx+3,at);for(unsigned i=0;i<n;i++)put16(tx+8+i*2,samples[at+i]);
            native_scan_release();
        }
    }else if((cmd==0x72 || cmd==0x73) && n && n<=48){
        if(cmd==0x73)at=value;
        unsigned limit=cmd==0x72?BAT68_BOOT_USER_OFFSET:BAT68_APP_SIZE;
        if(at<limit && n<=limit-at){memcpy(tx+8,(const void*)((cmd==0x72?0x200000u:0)+at),n);tx[2]=n;if(cmd==0x73)put32(tx+56,at);else put16(tx+3,at);}
    }else if(cmd==0x74){
        tx[2]=56;memcpy(tx+8,"B68Q",4);tx[12]=8;tx[13]=4;tx[14]=6;tx[15]=16;tx[16]=layer_state;tx[17]=1;tx[18]=bat68_host_queued()!=0;tx[19]=1;
        put16(tx+20,0xffff);put16(tx+22,0xffff);uint16_t rows[6];bat68_matrix_snapshot(rows);memcpy(tx+24,rows,12);
        put32(tx+36,native_scan_frames);put32(tx+48,bat68_eeprom_sequence());tx[52]=255;tx[53]=bat68_eeprom_dirty();tx[54]=1;tx[55]=2;put16(tx+56,0xd9);
        put32(tx+60,bat68_report_overflows);
    }else if((cmd==0x75 || cmd==0x76) && n<4 && r<6 && c<16){
        if(cmd==0x75 && bat68_physical_released()){dynamic_keymap_set_keycode(n,r,c,value);bat68_eeprom_request_save();}
        else if(cmd==0x75)return 1;
        tx[2]=2;tx[3]=r;tx[4]=c;put16(tx+8,dynamic_keymap_get_keycode(n,r,c));
    }else if(cmd==0x7b){tx[2]=24;bat68_usb_diagnostics(tx+8);
    }else if(cmd==0x7d){
        extern uint32_t bat68_he_frames,bat68_he_skipped_frames,bat68_main_loops,bat68_gated_loops;
        extern uint32_t bat68_queue_peak,bat68_axis_coalesced,bat68_flash_pages,bat68_flash_commits;
        extern uint32_t bat68_flash_max_page_ms,bat68_max_loop_gap_cycles;
        tx[2]=56;tx[8]=1;tx[9]=bat68_eeprom_dirty();
        uint32_t values[]={native_scan_frames,bat68_he_frames,bat68_he_skipped_frames,bat68_main_loops,
            bat68_gated_loops,bat68_queue_peak,bat68_axis_coalesced,bat68_flash_pages,bat68_flash_commits,
            bat68_flash_max_page_ms,bat68_max_loop_gap_cycles,bat68_host_queued(),HAL_RCC_GetHCLKFreq()};
        memcpy(tx+12,values,sizeof(values));
    }else if(cmd==0x7e){tx[2]=32;bat68_storage_diagnostics(tx+8);
    }else if(cmd==0x7f){
        tx[2]=56;tx[8]=1;tx[9]=native_scan_mode;
        if(n==0){
            uint32_t values[]={native_adc_cycles,native_adc_calls,native_adc_max_cycles,native_usb_irq_cycles,
                bat68_he_cycles,bat68_he_max_cycles,bat68_key_cycles,bat68_key_max_cycles,
                bat68_pre_cycles,bat68_post_cycles,HAL_RCC_GetHCLKFreq(),DWT->CYCCNT,HAL_GetTick()};
            memcpy(tx+12,values,sizeof(values));
        }else if(n==1){
            uint32_t values[]={SN_ADC0->CTRL,SN_ADC0->PRE,SN_ADC0->TPARM,SN_ADC0->SMPR,
                SN_ADC0->MISC,SN_ADC0->DISCHTIME,SN_ADC0->SQR0,SN_ADC0->SQR1,SN_ADC0->SQR2,SN_ADC0->SQR3,
                HAL_RCC_GetAPB1CLKFreq(),0,0};memcpy(tx+12,values,sizeof(values));
        }else if(n==2 && (value==0 || bat68_storage_released()) && !native_scan_configure(value)){
            tx[2]=1;tx[8]=1;
        }else tx[2]=255;
    }else if(cmd==0x79 && value==0x45564153u && bat68_storage_released()){
        int result=bat68_eeprom_save();if(result>=0){tx[2]=16;tx[8]=result;tx[9]=255;put32(tx+12,bat68_eeprom_sequence());}
    }else if(cmd==0x7a && value==0x54424552u && bat68_physical_released()){native_restart_requested=1;tx[2]=1;tx[8]=1;}
    return 1;
}
