// SPDX-License-Identifier: GPL-2.0-or-later
// Two independent 512-byte user-ROM pages. A save only replaces the inactive
// page; the previous complete record remains available after power loss.
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "keymap_settings.h"
#include "sn34_flash.h"

#define CONFIG_MAGIC 0x4b383642u
#define CONFIG_COMMIT 0xc0deb68au
#define CONFIG_WORDS (2u*6u*16u)
typedef struct {
    uint32_t magic;
    uint16_t version,size;
    uint32_t sequence,reserved;
    uint16_t keymap[CONFIG_WORDS];
    uint32_t crc,commit;
    uint8_t padding[104];
} config_record_t;
_Static_assert(sizeof(config_record_t)==512,"Config must occupy exactly one page");
_Static_assert(offsetof(config_record_t,crc)==400,"Unexpected config CRC coverage");
static config_record_t staging;
static uint32_t sequence;
static uint8_t current_slot;
static bool dirty;
static const uintptr_t pages[2]={0x7d000u,0x7d200u};

static uint32_t crc32(const void *source,unsigned count){
    const uint8_t *p=source;
    uint32_t crc=0xffffffffu;
    for(unsigned i=0;i<count;i++){
        crc^=p[i];
        for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1u)));
    }
    return ~crc;
}
static bool valid(const config_record_t *r){
    return r->magic==CONFIG_MAGIC&&r->version==1&&r->size==512&&r->commit==CONFIG_COMMIT&&
           r->crc==crc32(r,offsetof(config_record_t,crc));
}
void qmk_settings_init(void *keymap){
    const config_record_t *a=(const config_record_t*)pages[0],*b=(const config_record_t*)pages[1];
    bool va=valid(a),vb=valid(b);
    current_slot=0xff;sequence=0;dirty=false;
    if(va&&vb)current_slot=(int32_t)(b->sequence-a->sequence)>0?1:0;
    else if(va)current_slot=0;
    else if(vb)current_slot=1;
    if(current_slot!=0xff){
        const config_record_t *r=(const config_record_t*)pages[current_slot];
        sequence=r->sequence;memcpy(keymap,r->keymap,sizeof(r->keymap));
    }
}
void qmk_settings_changed(void){dirty=true;}
uint32_t qmk_settings_sequence(void){return sequence;}
uint8_t qmk_settings_slot(void){return current_slot;}
bool qmk_settings_dirty(void){return dirty;}

int qmk_settings_save(const void *keymap){
    if(current_slot!=0xff){
        const config_record_t *old=(const config_record_t*)pages[current_slot];
        if(valid(old)&&memcmp(old->keymap,keymap,sizeof(old->keymap))==0){dirty=false;return 0;}
    }
    memset(&staging,0xff,sizeof(staging));
    staging.magic=CONFIG_MAGIC;staging.version=1;staging.size=512;
    staging.sequence=sequence+1;staging.reserved=0;
    memcpy(staging.keymap,keymap,sizeof(staging.keymap));
    staging.crc=crc32(&staging,offsetof(config_record_t,crc));
    staging.commit=CONFIG_COMMIT;
    uint8_t target=current_slot==0?1:0;
    uint32_t saved;
    __asm__ volatile("mrs %0,primask\n cpsid i":"=r"(saved)::"memory");
    int result=sn34_flash_write_settings_page((unsigned)pages[target],&staging);
    __asm__ volatile("msr primask,%0"::"r"(saved):"memory");
    if(result)return -1;
    const config_record_t *written=(const config_record_t*)pages[target];
    if(!valid(written)||memcmp(written,&staging,sizeof(staging))!=0)return -1;
    sequence=written->sequence;current_slot=target;dirty=false;
    return 1;
}
