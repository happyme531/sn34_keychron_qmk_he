// SPDX-License-Identifier: GPL-2.0-or-later
// ASCII character classes for the freestanding newlib-header ABI. The target
// has no locale or hosted C library; extended bytes are not ASCII classes.
const char _ctype_[257]={
    [1 ... 9]=040,[10 ... 14]=040|010,[15 ... 32]=040,
    [' '+1]=010|0200,
    ['!'+1 ... '/'+1]=020,
    ['0'+1 ... '9'+1]=04,
    [':'+1 ... '@'+1]=020,
    ['A'+1 ... 'F'+1]=01|0100,['G'+1 ... 'Z'+1]=01,
    ['['+1 ... '`'+1]=020,
    ['a'+1 ... 'f'+1]=02|0100,['g'+1 ... 'z'+1]=02,
    ['{'+1 ... '~'+1]=020,[128]=040,
};
