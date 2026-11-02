// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34_he.h"
#include "via.h"
#include "raw_hid.h"
#include "keychron_raw_hid.h"
#include "rgb_protocol.h"
#include "sn34_eeprom.h"
#include "eeprom.h"
extern bool kc_raw_hid_rx(uint8_t src,uint8_t *data,uint8_t length);
static void reject(uint8_t *data,uint8_t length){data[0]=255;raw_hid_send(data,length);}

// Read-only settings snapshot protocol (B0), never an arbitrary Flash accessor.
// Revision checks let the host retry if calibration/configuration changes
// between packets, without locking input or allocating another EEPROM cache.
static void settings_snapshot(uint8_t *data) {
    uint8_t op = data[1], count = data[10];
    uint16_t offset;
    uint32_t expected;
    memcpy(&expected, data + 4, sizeof(expected));
    memcpy(&offset, data + 8, sizeof(offset));
    memset(data + 2, 0, RAW_EPSIZE - 2);
    data[3] = 1; // Protocol version.
    memcpy(data + 4, &sn34_eeprom_revision, sizeof(sn34_eeprom_revision));
    if (op == 0) {
        uint16_t size = EEPROM_SIZE, base = SN34_EEPROM_BASE;
        const uint32_t values[] = {SN34_EEPROM_BANK0, SN34_EEPROM_BANK1, SN34_EEPROM_MAGIC, SN34_EEPROM_COMMIT};
        memcpy(data + 8, &size, sizeof(size));
        memcpy(data + 10, &base, sizeof(base));
        data[12] = SN34_EEPROM_VERSION; // Layout of the live cache, even before its first commit.
        memcpy(data + 14, values, sizeof(values));
        data[30] = MATRIX_ROWS;
        data[31] = MATRIX_COLS;
    } else if (op != 1 || !count || count > RAW_EPSIZE - 10 || offset > EEPROM_SIZE || count > EEPROM_SIZE - offset) {
        data[2] = 1;
    } else if (expected != sn34_eeprom_revision) {
        data[2] = 3; // Snapshot changed; start again from INFO.
    } else {
        memcpy(data + 8, &offset, sizeof(offset));
        eeprom_read_block(data + 10, (void *)(uintptr_t)offset, count);
    }
    raw_hid_send(data, RAW_EPSIZE);
}
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
    if(data[0]==0xb0){settings_snapshot(data);return true;}
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
