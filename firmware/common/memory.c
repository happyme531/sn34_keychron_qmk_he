// SPDX-License-Identifier: GPL-2.0-or-later
// Freestanding C memory primitives shared by the native and historical builds.
#include <stddef.h>
#include <stdint.h>
typedef uint32_t alias_word __attribute__((__may_alias__));
void *memcpy(void *d,const void *s,size_t n) {
    unsigned char *a=d;const unsigned char *b=s;
    if(!(((uintptr_t)a^(uintptr_t)b)&3u)){
        while(n && ((uintptr_t)a&3u)){*a++=*b++;n--;}
        while(n>=4){*(alias_word*)a=*(const alias_word*)b;a+=4;b+=4;n-=4;}
    }
    while(n--)*a++=*b++;return d;
}
void *memset(void *d,int v,size_t n) {
    unsigned char *a=d;
    while(n && ((uintptr_t)a&3u)){*a++=(unsigned char)v;n--;}
    uint32_t word=(uint8_t)v*0x01010101u;
    while(n>=4){*(alias_word*)a=word;a+=4;n-=4;}
    while(n--)*a++=(unsigned char)v;return d;
}
int memcmp(const void *a,const void *b,size_t n) {
    const unsigned char *x=a,*y=b;
    for(size_t i=0;i<n;i++)if(x[i]!=y[i])return x[i]<y[i]?-1:1;return 0;
}
void *memmove(void *d,const void *s,size_t n) {
    unsigned char *a=d;const unsigned char *b=s;
    if(a<b)for(size_t i=0;i<n;i++)a[i]=b[i];
    else for(size_t i=n;i;i--)a[i-1]=b[i-1];return d;
}
void __aeabi_memcpy(void *d,const void*s,size_t n){memcpy(d,s,n);}
void __aeabi_memcpy4(void *d,const void*s,size_t n){memcpy(d,s,n);}
void __aeabi_memclr(void *d,size_t n){memset(d,0,n);}
void __aeabi_memclr4(void *d,size_t n){memset(d,0,n);}
