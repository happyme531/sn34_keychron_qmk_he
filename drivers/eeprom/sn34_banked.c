// SPDX-License-Identifier: GPL-2.0-or-later
// QMK EEPROM cache, saved to two banks from the board storage contract. Each
// commit page is written last. Boot, footer and legacy keymap pages are excluded.
#include "quantum.h"
#include "eeprom.h"
#include "sn34_eeprom.h"
#include "sn34_flash.h"
#include "sn34f28x_hal.h"

#include "nvm_eeprom_eeconfig_internal.h"
enum { PAGE_SIZE=SN34_PAGE_SIZE, MAGIC=SN34_EEPROM_MAGIC, COMMIT=SN34_EEPROM_COMMIT, FORMAT_VERSION=SN34_EEPROM_VERSION };
typedef struct { uint32_t magic, version, sequence, size, crc, commit, header_crc; uint8_t padding[PAGE_SIZE - 7*sizeof(uint32_t)]; } header_t;
_Static_assert(sizeof(header_t) == PAGE_SIZE, "EEPROM header page size");
static uint8_t cache[EEPROM_SIZE];
static const uintptr_t banks[] = {SN34_EEPROM_BANK0, SN34_EEPROM_BANK1};
static uint32_t sequence;
static int current = -1;
static bool cached_dirty;
uint32_t sn34_eeprom_revision;
static uint8_t staged[EEPROM_SIZE];
static header_t staged_header;
static int staged_bank=-1;
static unsigned staged_page;
static uint32_t staged_revision;

static uint32_t crc32(const void *source, unsigned size) {
    const uint8_t *p = source; uint32_t crc = ~0u;
    while (size--) { crc ^= *p++; for (unsigned b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1))); }
    return ~crc;
}
static bool valid(unsigned bank) {
    const header_t *h = (const header_t *)(banks[bank] + EEPROM_SIZE);
    return h->magic == MAGIC && (h->version == FORMAT_VERSION || h->version == 1 || h->version == 2) && h->size == EEPROM_SIZE && h->commit == COMMIT &&
           h->header_crc == crc32(h, offsetof(header_t, header_crc)) &&
           h->crc == crc32((const void *)banks[bank], EEPROM_SIZE);
}
void sn34_eeprom_init(void) {
    staged_bank=-1;
    bool a = valid(0), b = valid(1);
    current = a ? 0 : b ? 1 : -1;
    if (a && b) {
        const header_t *ha = (const header_t *)(banks[0] + EEPROM_SIZE), *hb = (const header_t *)(banks[1] + EEPROM_SIZE);
        if ((int32_t)(hb->sequence - ha->sequence) > 0) current = 1;
    }
    sequence = 0;
    cached_dirty=current<0;
    memset(cache, 0, sizeof(cache));
    if (current >= 0) {
        memcpy(cache, (const void *)banks[current], sizeof(cache));
        sequence = ((const header_t *)(banks[current] + EEPROM_SIZE))->sequence;
        cached_dirty = sn34_eeprom_version() != FORMAT_VERSION;
    }

}
void eeprom_read_block(void *dst, const void *src, size_t size) {
    uintptr_t offset = (uintptr_t)src;
    if (offset <= sizeof(cache) && size <= sizeof(cache) - offset) memcpy(dst, cache + offset, size);
    else memset(dst, 0, size);
}
void eeprom_update_block(const void *src, void *dst, size_t size) {
    uintptr_t offset = (uintptr_t)dst;
    if (offset <= sizeof(cache) && size <= sizeof(cache) - offset && memcmp(cache+offset,src,size)) {
        memcpy(cache + offset, src, size);cached_dirty=true;sn34_eeprom_revision++;
    }
}
void eeprom_write_block(const void *src, void *dst, size_t size) { eeprom_update_block(src, dst, size); }
#define EEPROM_SCALAR(type, name) \
type eeprom_read_##name(const type *p) { type v; eeprom_read_block(&v, p, sizeof(v)); return v; } \
void eeprom_update_##name(type *p, type v) { eeprom_update_block(&v, p, sizeof(v)); } \
void eeprom_write_##name(type *p, type v) { eeprom_update_##name(p, v); }
EEPROM_SCALAR(uint8_t, byte)
EEPROM_SCALAR(uint16_t, word)
EEPROM_SCALAR(uint32_t, dword)
void eeprom_driver_init(void) { sn34_eeprom_init(); }
void eeprom_driver_erase(void) {
    memset(cache, 0, sizeof(cache));cached_dirty=true;
    sn34_eeprom_revision++;staged_bank=-1;
}
void eeprom_driver_format(bool erase) { (void)erase; eeprom_driver_erase(); }
bool sn34_eeprom_dirty(void) { return cached_dirty; }
uint32_t sn34_eeprom_version(void) {
    return current < 0 ? FORMAT_VERSION : ((const header_t *)(banks[current] + EEPROM_SIZE))->version;
}
static int save_page(uint32_t offset,const void *data){
    uint32_t irq=__get_PRIMASK();__disable_irq();
    int result=sn34_flash_write_eeprom_page(offset,data);
    __set_PRIMASK(irq);
    return result || memcmp((const void *)offset,data,PAGE_SIZE)?-1:0;
}
// Background saves perform at most one physical page write per call. The
// previous committed bank stays valid until the final header is committed.
int sn34_eeprom_save_step(void) {
    if (!sn34_eeprom_dirty()) return 0;
    if(staged_bank<0 || staged_revision!=sn34_eeprom_revision){
        if(current>=0 && sn34_eeprom_version()==FORMAT_VERSION && !memcmp(cache,(const void *)banks[current],sizeof(cache))){cached_dirty=false;staged_bank=-1;return 0;}
        memcpy(staged,cache,sizeof(staged));staged_bank=current==0?1:0;staged_page=0;
        staged_revision=sn34_eeprom_revision;
        staged_header=(header_t){.magic=MAGIC,.version=FORMAT_VERSION,.sequence=sequence+1,.size=EEPROM_SIZE,
            .crc=crc32(staged,sizeof(staged)),.commit=COMMIT};
        staged_header.header_crc=crc32(&staged_header,offsetof(header_t,header_crc));
    }
    while(staged_page<sizeof(staged)/PAGE_SIZE){
        unsigned offset=staged_page++*PAGE_SIZE;
        if(!memcmp((const void *)(banks[staged_bank]+offset),staged+offset,PAGE_SIZE))continue;
        if(save_page(banks[staged_bank]+offset,staged+offset)){staged_bank=-1;return -1;}
        return 0;
    }
    unsigned target=staged_bank;
    if(save_page(banks[target]+EEPROM_SIZE,&staged_header) || !valid(target)) {staged_bank=-1;return -1;}
    current=target;sequence=staged_header.sequence;cached_dirty=false;staged_bank=-1;
    return 1;
}
