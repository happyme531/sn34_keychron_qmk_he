// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34_he.h"
#include "analog_matrix.h"
#include "via.h"
#include "raw_hid.h"
#include "keychron_raw_hid.h"
#include "rgb_protocol.h"
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
bool via_command_kb(uint8_t src,uint8_t *data,uint8_t length){
    if(length!=RAW_EPSIZE)return true;
    if(data[0]==id_custom_set_value && data[1]==3 && data[2]==2){
        if(data[3]>=sizeof(sn34_rgb_wire_to_core) || sn34_rgb_wire_to_core[data[3]]==255){reject(data,length);return true;}
        data[3]=sn34_rgb_wire_to_core[data[3]];
    }
    if(data[0]==KC_MISC_CMD_GROUP && data[1]==NKRO_SET &&
       (!sn34_physical_released() || !sn34_matrix_released())){
        data[2]=KC_FAIL;raw_hid_send(data,length);return true;
    }
    return kc_raw_hid_rx(src,data,length);
}
void kc_analog_matrix_rx(uint8_t *data,uint8_t length){
    if(length!=RAW_EPSIZE)return;
    uint8_t cmd=data[1];
    if(cmd==AMC_CALIBRATE && data[2]==2 && !sn34_physical_released()){reject(data,length);return;}
    bool modifying=cmd==AMC_SELECT_PROFILE || (cmd>=AMC_SET_PROFILE_NAME && cmd<=AMC_SET_SOCD) ||
        cmd==AMC_RESET_PROFILE || cmd==AMC_SAVE_PROFILE || cmd==AMC_SET_CURVE || cmd==AMC_SET_GAME_CONTROLLER_MODE;
    if(modifying &&
       (!sn34_physical_released() || !sn34_matrix_released())){data[0]=255;raw_hid_send(data,length);return;}
    analog_matrix_rx(data,length);
}
