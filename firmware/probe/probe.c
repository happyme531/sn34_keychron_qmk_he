/* BAT68 diagnostic extension for a SHA256-pinned stock application.
 * No startup code, persistent storage, clock changes, or flash operations.
 * Commands require the B68 tag; all other traffic follows the original path.
 */
#include <stdint.h>
#include "profile.h"

#define RX ((volatile uint8_t *)RX_ADDR)
#define TX ((volatile uint8_t *)TX_ADDR)
#define PENDING (*(volatile uint8_t *)PENDING_ADDR)
#define READY (*(volatile uint8_t *)READY_ADDR)
#define RAW ((volatile uint16_t *)RAW_ADDR)
#define BOOT_BASE 0x00200000u
#define BOOT_SIZE 0x2000u
#define APP_SIZE 0x7e000u

static void put16(unsigned p, unsigned v) {
    TX[p] = (uint8_t)v;
    TX[p + 1] = (uint8_t)(v >> 8);
}

__attribute__((used, noinline))
int probe_handle(void) {
    if (!PENDING || RX[0] != 0xaa || RX[5] != 'B' || RX[6] != '6' || RX[7] != '8')
        return 0;
    unsigned cmd = RX[1];
    if (cmd < 0x70 || cmd > 0x73)
        return 0;

    unsigned count = RX[2];
    unsigned offset = RX[3] | ((unsigned)RX[4] << 8);
    PENDING = 0;
    for (unsigned i = 0; i < 64; i++) TX[i] = 0;
    TX[0] = 0x55;
    TX[1] = (uint8_t)cmd;
    TX[5] = 'B'; TX[6] = '6'; TX[7] = '8';
    put16(3, offset);

    if (cmd == 0x70) {
        TX[2] = 24;
        TX[8] = 'B'; TX[9] = '6'; TX[10] = '8'; TX[11] = 'P';
        TX[12] = 2;                 /* protocol version; adds bounded app ROM read */
        TX[13] = 96;                /* raw ADC slots */
        TX[14] = 128;               /* electrical key positions */
        TX[15] = 48;                /* maximum payload bytes */
        put16(16, STOCK_BCD_VERSION);
        put16(18, BOOT_SIZE);
        /* First 8 bytes of the pinned stock image SHA256. */
        static const uint8_t hash[8] = {STOCK_HASH_BYTES};
        for (unsigned i=0;i<8;i++) TX[20+i]=hash[i];
        TX[28]=0x00; TX[29]=0x80; TX[30]=0x01; TX[31]=0x00;
    } else if (cmd == 0x71) {
        /* Count and offset are in u16 slots, not bytes. */
        if (!count || count > 24 || offset >= 96 || count > 96 - offset) {
            TX[2] = 0xff;
        } else {
            uint32_t saved;
            __asm__ volatile("mrs %0, primask\n cpsid i" : "=r"(saved) :: "memory");
            for (unsigned i = 0; i < count; i++) put16(8 + 2*i, RAW[offset+i]);
            __asm__ volatile("msr primask, %0" :: "r"(saved) : "memory");
            TX[2] = (uint8_t)(2*count);
        }
    } else if (cmd == 0x72) {
        /* Explicit Boot-region read. Never exposes an arbitrary address.
         * Read protection may still fault on real silicon: host must opt in.
         */
        if (!count || count > 48 || offset >= BOOT_SIZE || count > BOOT_SIZE - offset) {
            TX[2] = 0xff;
        } else {
            volatile const uint8_t *source = (volatile const uint8_t *)(BOOT_BASE + offset);
            for (unsigned i=0; i<count; i++) TX[8+i] = source[i];
            TX[2] = (uint8_t)count;
        }
    } else {
        /* User ROM only. The 32-bit offset is independent of the u16 slot
         * offset used by other commands. No MMIO or arbitrary memory access.
         */
        uint32_t address = RX[8] | ((uint32_t)RX[9]<<8) |
                           ((uint32_t)RX[10]<<16) | ((uint32_t)RX[11]<<24);
        if (!count || count>48 || address>=APP_SIZE || count>APP_SIZE-address) {
            TX[2]=0xff;
        } else {
            volatile const uint8_t *source=(volatile const uint8_t *)(uintptr_t)address;
            for (unsigned i=0;i<count;i++) TX[8+i]=source[i];
            TX[2]=(uint8_t)count;
            put16(56,address);put16(58,address>>16);
        }
    }
    READY = 1;
    return 1;
}
