// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "keymap.generated.h"

// Definitions are part of the ordinary QMK keymap introspection unit. They can
// be assigned with VIA without adding special cases to the event dispatcher.
tap_dance_action_t tap_dance_actions[]={ACTION_TAP_DANCE_DOUBLE(KC_ESC,KC_CAPS)};
// Optional combo definition; F23/F24 can be assigned through VIA. Keeping
// ordinary modifiers out of it avoids adding combo latency to normal typing.
const uint16_t PROGMEM caps_combo[]={KC_F23,KC_F24,COMBO_END};
combo_t key_combos[]={COMBO(caps_combo,KC_CAPS)};

