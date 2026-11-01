// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "platform.h"
#include "analog_matrix.h"
#include "profile.h"
#include "via.h"
#include "raw_hid.h"
#include "keychron_raw_hid.h"
#include "rgb_protocol.generated.h"
extern bool kc_raw_hid_rx(uint8_t src,uint8_t *data,uint8_t length);
static void reject(uint8_t *data,uint8_t length){data[0]=255;raw_hid_send(data,length);}
// Only the configurator protocol is translated. QMK keys, animations and the
// persistent configuration continue to use their original internal IDs.
void via_raw_hid_send(uint8_t src,uint8_t *data,uint8_t length){
    (void)src;
    if(length>=4 && (data[0]==id_custom_get_value || data[0]==id_custom_set_value) && data[1]==3 && data[2]==2){
        if(data[3]>=sizeof(sn34_rgb_core_to_wire)){reject(data,length);return;}
        data[3]=sn34_rgb_core_to_wire[data[3]];
    }
    raw_hid_send(data,length);
}
// Board adapters only translate RGB IDs and validate configuration writes.
// Keychron owns Launcher identity/capabilities/dispatch and matrix queries;
// QMK VIA owns ordinary keymaps, macros and RGB configuration commands.
void sn34_raw_hid_receive(uint8_t *data,uint8_t length){
    if(length!=32)return;
    if(data[0]==id_custom_set_value && data[1]==3 && data[2]==2){
        if(data[3]>=sizeof(sn34_rgb_wire_to_core) || sn34_rgb_wire_to_core[data[3]]==255){reject(data,length);return;}
        data[3]=sn34_rgb_wire_to_core[data[3]];
    }
    raw_hid_receive(RAW_HID_SRC_USB,data,length);
}
bool via_command_kb(uint8_t src,uint8_t *data,uint8_t length){
    if(data[0]==KC_MISC_CMD_GROUP && data[1]==NKRO_SET &&
       (!sn34_physical_released() || !sn34_matrix_released())){
        data[2]=KC_FAIL;raw_hid_send(data,length);return true;
    }
    return kc_raw_hid_rx(src,data,length);
}
void kc_analog_matrix_rx(uint8_t *data,uint8_t length){
    sn34_he_raw_receive(data,length);
}
void sn34_he_raw_receive(uint8_t *data,uint8_t length){
    if(data[1]==0x12){
        unsigned offset=data[3]|(data[4]<<8),requested=data[5];
        if(data[2]>=PROFILE_COUNT || requested>30 || offset+requested>PROFILE_SIZE){reject(data,length);return;}
        // Official Launcher requests 30 bytes for a profile name, but consumes
        // only the 26 bytes available after its six-byte response header.
        // Echo its requested length for compatibility while bounding both the
        // upstream memset and memcpy to the physical packet capacity.
        unsigned copied=requested>length-6?length-6:requested;
        if(!profile_get_raw_data(data[2],offset,copied,data+6)){reject(data,length);return;}
        raw_hid_send(data,length);return;
    }
    if(data[1]==0x14 && (data[2]>=PROFILE_COUNT || data[3]>AKM_RAPID || data[4]>39 || data[5]>39 || data[6]>39 ||
       (data[7] && (!data[3] || !data[4] || !data[5])))){reject(data,length);return;}
    if(data[1]==0x15 && data[3]==1){
        unsigned a=data[7],d=data[8],b=data[9],e=data[10];
        if(!a || a>39 || d>=a || b<=a || b>40 || e<d || e>=b){reject(data,length);return;}
    }
    if(data[1]==0x21){
        for(unsigned i=0;i<4;i++)if(data[2+i*2]>40 || data[3+i*2]>127){reject(data,length);return;}
        for(unsigned i=0;i<3;i++)if(data[2+i*2]>=data[4+i*2]){reject(data,length);return;}
    }
    if(data[1]==0x23 && (data[2]&~3u)){reject(data,length);return;}
    if(data[1]==0x40 && data[2]==2 && !sn34_physical_released()){reject(data,length);return;}
    bool modifying=data[1]==0x11 || (data[1]>=0x13 && data[1]<=0x16) || data[1]==0x1e || data[1]==0x1f || data[1]==0x21 || data[1]==0x23;
    if(modifying &&
       (!sn34_physical_released() || !sn34_matrix_released())){data[0]=255;raw_hid_send(data,length);return;}
    unsigned cmd=data[1];bool global=cmd==0x14 && data[7];
    analog_matrix_rx(data,length);
    if(global)update_travel_configs();
}
