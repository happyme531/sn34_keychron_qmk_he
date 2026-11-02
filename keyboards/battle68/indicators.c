// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "sn34f28x_hal.h"
void keyboard_pre_init_kb(void){
    SN_GPIO1->BCLR=(1u<<6)|(1u<<10)|(1u<<11);
    SN_GPIO1->DIR|=(1u<<6)|(1u<<10)|(1u<<11);
    keyboard_pre_init_user();
}
void sn34_indicators_task(void){
    unsigned on=(host_keyboard_led_state().caps_lock?(1u<<6):0)|
        (keymap_config.no_gui?(1u<<10):0)|((default_layer_state&(1u<<SN34_MAC_BASE_LAYER))?(1u<<11):0);
    unsigned mask=(1u<<6)|(1u<<10)|(1u<<11);
    SN_GPIO1->BSET=on;SN_GPIO1->BCLR=mask&~on;
}
