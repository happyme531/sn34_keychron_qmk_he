// SPDX-License-Identifier: GPL-2.0-or-later
#include <stddef.h>
#include <stdint.h>
#include "sn34f28x_hal.h"
typedef struct block {uint32_t size;uint32_t used;} block_t;
static union {uint64_t align;uint8_t bytes[32768];} arena;
static uint8_t heap_initialized;
volatile uint32_t native_log_calls;
void *malloc(size_t count){
    if(!count||count>sizeof(arena.bytes)-sizeof(block_t))return NULL;
    count=(count+7u)&~7u;
    uint32_t saved=__get_PRIMASK();__disable_irq();
    if(!heap_initialized){((block_t*)arena.bytes)->size=sizeof(arena.bytes)-sizeof(block_t);heap_initialized=1;}
    uint8_t *at=arena.bytes;
    while(at<arena.bytes+sizeof(arena.bytes)){
        block_t *b=(block_t*)at;
        if(!b->used&&b->size>=count){
            if(b->size>=count+sizeof(block_t)+8){
                block_t *next=(block_t*)(at+sizeof(block_t)+count);
                next->size=b->size-count-sizeof(block_t);next->used=0;b->size=count;
            }
            b->used=1;__set_PRIMASK(saved);return at+sizeof(block_t);
        }
        at+=sizeof(block_t)+b->size;
    }
    __set_PRIMASK(saved);return NULL;
}
void free(void *pointer){
    if(!pointer)return;
    uint8_t *p=pointer;
    if(p<arena.bytes+sizeof(block_t)||p>=arena.bytes+sizeof(arena.bytes))return;
    uint32_t saved=__get_PRIMASK();__disable_irq();
    ((block_t*)(p-sizeof(block_t)))->used=0;
    uint8_t *at=arena.bytes;
    while(at<arena.bytes+sizeof(arena.bytes)){
        block_t *b=(block_t*)at;
        uint8_t *next=at+sizeof(block_t)+b->size;
        if(!b->used&&next<arena.bytes+sizeof(arena.bytes)&&!((block_t*)next)->used){
            b->size+=sizeof(block_t)+((block_t*)next)->size;continue;
        }
        at=next;
    }
    __set_PRIMASK(saved);
}
size_t strlen(const char *s){size_t n=0;while(s[n])n++;return n;}
int printf(const char *format,...){(void)format;native_log_calls++;return 0;}
