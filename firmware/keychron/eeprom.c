// SPDX-License-Identifier: GPL-2.0-or-later
// QMK EEPROM cache, saved to two banks from the board storage contract. Each
// commit page is written last. Boot, footer and legacy keymap pages are excluded.
#include "quantum.h"
#include "analog_matrix.h"
#include "eeprom.h"
#include "bat68_eeprom.h"
#include "hall.generated.h"
#include "sn34_flash.h"
#include "sn34f28x_hal.h"

#if BAT68_QMK_PLATFORM
#include "nvm_eeprom_eeconfig_internal.h"
enum { PAGE_SIZE=BAT68_PAGE_SIZE, MAGIC=BAT68_EEPROM_MAGIC, COMMIT=BAT68_EEPROM_COMMIT, FORMAT_VERSION=BAT68_EEPROM_VERSION };
_Static_assert((uintptr_t)EECONFIG_KB_DATABLOCK == BAT68_EEPROM_BASE, "QMK core EEPROM layout changed");
_Static_assert((uintptr_t)EECONFIG_RGB_MATRIX == BAT68_RGB_CORE_OFFSET, "QMK RGB EEPROM offset changed");
_Static_assert((uintptr_t)EECONFIG_RGB_MATRIX + offsetof(rgb_config_t, hsv.v) == BAT68_RGB_VALUE_OFFSET, "QMK RGB value offset changed");
_Static_assert(KC_ANALOG_MATRIX_VERSION == BAT68_HE_VERSION, "Keychron HE ABI changed");
_Static_assert(OFFSET_CALIBRATED_DATA_START == BAT68_HE_CALIBRATION_OFFSET, "Calibration ABI changed");
_Static_assert(OFFSET_PROFILES_START == BAT68_HE_PROFILES_OFFSET && PROFILE_SIZE == BAT68_HE_PROFILE_SIZE, "Profile ABI changed");
_Static_assert(OFFSET_CURVE_PTS_START == BAT68_HE_CURVE_OFFSET, "Curve ABI changed");
_Static_assert(OFFSET_GAME_CONTROLLER_MODE_START == BAT68_HE_CONTROLLER_OFFSET && EECONFIG_SIZE_ANALOG_MATRIX == BAT68_HE_SIZE, "HE storage size changed");
#else
// Archived HE builds retain their original physical storage layout.
enum { PAGE_SIZE=512, MAGIC=0x45483842, COMMIT=0x4845434d, FORMAT_VERSION=1 };
#endif
typedef struct { uint32_t magic, version, sequence, size, crc, commit, header_crc; uint8_t padding[PAGE_SIZE - 7*sizeof(uint32_t)]; } header_t;
_Static_assert(sizeof(header_t) == PAGE_SIZE, "EEPROM header page size");
_Static_assert(EECONFIG_BASE_ANALOG_MATRIX + EECONFIG_SIZE_ANALOG_MATRIX <= EEPROM_SIZE, "EEPROM fits bank");
_Static_assert(sizeof(calibrated_value_t) == SIZE_OF_CALIB_VALUE_T, "Keychron calibration layout");
static uint8_t cache[EEPROM_SIZE], external[EXTERNAL_EEPROM_OFFSET + OFFSET_CALIBRATED_DATA_END];
#if BAT68_QMK_PLATFORM
static const uintptr_t banks[] = {BAT68_EEPROM_BANK0, BAT68_EEPROM_BANK1};
#else
static const uintptr_t banks[] = {0x7b000, 0x7c000};
#endif
static uint32_t sequence;
static int current = -1;
static bool cached_dirty;
uint32_t bat68_eeprom_revision;
static uint8_t staged[EEPROM_SIZE];
static header_t staged_header;
static int staged_bank=-1;
static unsigned staged_page;
static uint32_t staged_revision;
uint32_t bat68_flash_pages,bat68_flash_commits,bat68_flash_max_page_ms;

static uint32_t crc32(const void *source, unsigned size) {
    const uint8_t *p = source; uint32_t crc = ~0u;
    while (size--) { crc ^= *p++; for (unsigned b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1))); }
    return ~crc;
}
static bool valid(unsigned bank) {
    const header_t *h = (const header_t *)(banks[bank] + EEPROM_SIZE);
    return h->magic == MAGIC && h->version == FORMAT_VERSION && h->size == EEPROM_SIZE && h->commit == COMMIT &&
           h->header_crc == crc32(h, offsetof(header_t, header_crc)) &&
           h->crc == crc32((const void *)banks[bank], EEPROM_SIZE);
}
void bat68_eeprom_init(void) {
    staged_bank=-1;
    bool a = valid(0), b = valid(1);
    current = a ? 0 : b ? 1 : -1;
    if (a && b) {
        const header_t *ha = (const header_t *)(banks[0] + EEPROM_SIZE), *hb = (const header_t *)(banks[1] + EEPROM_SIZE);
        if ((int32_t)(hb->sequence - ha->sequence) > 0) current = 1;
    }
    sequence = 0;
    cached_dirty=current<0;
    memset(cache, 0, sizeof(cache)); memset(external, 0, sizeof(external));
    if (current >= 0) {
        memcpy(cache, (const void *)banks[current], sizeof(cache));
        sequence = ((const header_t *)(banks[current] + EEPROM_SIZE))->sequence;
    }
    // There is no I2C calibration EEPROM on this board. Provide Keychron's
    // fallback with the per-key released measurements and estimated bottoms.
    uint32_t vendor = VENDOR_ID; memcpy(external, &vendor, 4);
    external[4 + OFFSET_CALIBRATION] = 1; // Released references known; bottom still estimated.
    calibrated_value_t *values = (calibrated_value_t *)(external + 4 + OFFSET_CALIBRATED_DATA_START);
    for (unsigned i = 0; i < BAT68_HALL_KEYS; i++) {
        values[hall_keys[i].slot].zero_travel = hall_keys[i].idle;
        values[hall_keys[i].slot].full_travel = hall_keys[i].bottom;
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
        memcpy(cache + offset, src, size);cached_dirty=true;bat68_eeprom_revision++;
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
void eeprom_driver_init(void) {}
void eeprom_driver_erase(void) {
    memset(cache, 0, sizeof(cache));cached_dirty=true;
    bat68_eeprom_revision++;staged_bank=-1;
}
void eeprom_driver_format(bool erase) { (void)erase; eeprom_driver_erase(); }
void he_eeprom_driver_init(void) {}
void he_eeprom_driver_erase(void) { memset(external, 0, sizeof(external)); }
void he_eeprom_read_block(void *dst, const void *src, size_t size) {
    uintptr_t offset = (uintptr_t)src;
    if (offset <= sizeof(external) && size <= sizeof(external) - offset) memcpy(dst, external + offset, size);
    else memset(dst, 0, size);
}
void he_eeprom_write_block(const void *src, void *dst, size_t size) {
    uintptr_t offset = (uintptr_t)dst;
    if (offset <= sizeof(external) && size <= sizeof(external) - offset) memcpy(external + offset, src, size);
}
bool bat68_eeprom_dirty(void) { return cached_dirty; }
uint32_t bat68_eeprom_sequence(void) { return sequence; }
static int save_page(uint32_t offset,const void *data){
    uint32_t started=HAL_GetTick(),irq=__get_PRIMASK();__disable_irq();
    int result=sn34_flash_write_eeprom_page(offset,data);
    __set_PRIMASK(irq);
    uint32_t duration=HAL_GetTick()-started;
    if(duration>bat68_flash_max_page_ms)bat68_flash_max_page_ms=duration;
    bat68_flash_pages++;
    return result || memcmp((const void *)offset,data,PAGE_SIZE)?-1:0;
}
// Background saves perform at most one physical page write per call. The
// previous committed bank stays valid until the final header is committed.
int bat68_eeprom_save_step(void) {
    if (!bat68_eeprom_dirty()) return 0;
    if(staged_bank<0 || staged_revision!=bat68_eeprom_revision){
        if(current>=0 && !memcmp(cache,(const void *)banks[current],sizeof(cache))){cached_dirty=false;staged_bank=-1;return 0;}
        memcpy(staged,cache,sizeof(staged));staged_bank=current==0?1:0;staged_page=0;
        staged_revision=bat68_eeprom_revision;
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
    current=target;sequence=staged_header.sequence;cached_dirty=false;staged_bank=-1;bat68_flash_commits++;
    return 1;
}
int bat68_eeprom_save(void) {
    int written=0;
    while(bat68_eeprom_dirty()){
        int result=bat68_eeprom_save_step();if(result<0)return result;if(result>0)written=1;
    }
    return written;
}
