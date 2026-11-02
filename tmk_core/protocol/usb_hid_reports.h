/*
 * Copyright 2012 Jun Wako <wakojun@gmail.com>
 * This file is based on:
 *     LUFA-120219/Demos/Device/Lowlevel/KeyboardMouse
 *     LUFA-120219/Demos/Device/Lowlevel/GenericHID
 */

/*
                         LUFA Library
         Copyright (C) Dean Camera, 2012.

    dean [at] fourwalledcubicle [dot] com
                     www.lufa-lib.org
*/

/*
    Copyright 2012  Dean Camera (dean [at] fourwalledcubicle [dot] com)
    Copyright 2010  Denver Gingerich (denver [at] ossguy [dot] com)

    Permission to use, copy, modify, distribute, and sell this
    software and its documentation for any purpose is hereby granted
    without fee, provided that the above copyright notice appear in
    all copies and that both that the copyright notice and this
    permission notice and warranty disclaimer appear in supporting
    documentation, and that the name of the author not be used in
    advertising or publicity pertaining to distribution of the
    software without specific, written prior permission.

    The author disclaim all warranties with regard to this
    software, including all implied warranties of merchantability
    and fitness.  In no event shall the author be liable for any
    special, indirect or consequential damages or any damages
    whatsoever resulting from loss of use, data or profits, whether
    in an action of contract, negligence or other tortious action,
    arising out of or in connection with the use or performance of
    this software.
*/

#pragma once
#include "report.h"
#include "usb_descriptor_common.h"
#define __INCLUDE_FROM_USB_DRIVER
#define __INCLUDE_FROM_HID_DRIVER
#include "lib/lufa/LUFA/Drivers/USB/Class/Common/HIDReportData.h"
// clang-format off

/*
 * HID report descriptors
 */
#ifdef KEYBOARD_SHARED_EP
const USB_Descriptor_HIDReport_Datatype_t PROGMEM SharedReport[] = {
#    define SHARED_REPORT_STARTED
#else
const USB_Descriptor_HIDReport_Datatype_t PROGMEM KeyboardReport[] = {
#endif
    HID_RI_USAGE_PAGE(8, 0x01),        // Generic Desktop
    HID_RI_USAGE(8, 0x06),             // Keyboard
    HID_RI_COLLECTION(8, 0x01),        // Application
#ifdef KEYBOARD_SHARED_EP
        HID_RI_REPORT_ID(8, REPORT_ID_KEYBOARD),
#endif
        // Modifiers (8 bits)
        HID_RI_USAGE_PAGE(8, 0x07),    // Keyboard/Keypad
        HID_RI_USAGE_MINIMUM(8, 0xE0), // Keyboard Left Control
        HID_RI_USAGE_MAXIMUM(8, 0xE7), // Keyboard Right GUI
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(8, 0x01),
        HID_RI_REPORT_COUNT(8, 0x08),
        HID_RI_REPORT_SIZE(8, 0x01),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
        // Reserved (1 byte)
        HID_RI_REPORT_COUNT(8, 0x01),
        HID_RI_REPORT_SIZE(8, 0x08),
        HID_RI_INPUT(8, HID_IOF_CONSTANT),
        // Keycodes (6 bytes)
        HID_RI_USAGE_PAGE(8, 0x07),    // Keyboard/Keypad
        HID_RI_USAGE_MINIMUM(8, 0x00),
        HID_RI_USAGE_MAXIMUM(8, 0xFF),
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(16, 0x00FF),
        HID_RI_REPORT_COUNT(8, 0x06),
        HID_RI_REPORT_SIZE(8, 0x08),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_ARRAY | HID_IOF_ABSOLUTE),

        // Status LEDs (5 bits)
        HID_RI_USAGE_PAGE(8, 0x08),    // LED
        HID_RI_USAGE_MINIMUM(8, 0x01), // Num Lock
        HID_RI_USAGE_MAXIMUM(8, 0x05), // Kana
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(8, 0x01),
        HID_RI_REPORT_COUNT(8, 0x05),
        HID_RI_REPORT_SIZE(8, 0x01),
        HID_RI_OUTPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE | HID_IOF_NON_VOLATILE),
        // LED padding (3 bits)
        HID_RI_REPORT_COUNT(8, 0x01),
        HID_RI_REPORT_SIZE(8, 0x03),
        HID_RI_OUTPUT(8, HID_IOF_CONSTANT),
    HID_RI_END_COLLECTION(0),
#ifndef KEYBOARD_SHARED_EP
};
#endif

#ifdef MOUSE_ENABLE
#    ifndef MOUSE_SHARED_EP
const USB_Descriptor_HIDReport_Datatype_t PROGMEM MouseReport[] = {
#    elif !defined(SHARED_REPORT_STARTED)
const USB_Descriptor_HIDReport_Datatype_t PROGMEM SharedReport[] = {
#        define SHARED_REPORT_STARTED
#    endif
    HID_RI_USAGE_PAGE(8, 0x01),            // Generic Desktop
    HID_RI_USAGE(8, 0x02),                 // Mouse
    HID_RI_COLLECTION(8, 0x01),            // Application
#    ifdef MOUSE_SHARED_EP
        HID_RI_REPORT_ID(8, REPORT_ID_MOUSE),
#    endif
        HID_RI_USAGE(8, 0x01),             // Pointer
        HID_RI_COLLECTION(8, 0x00),        // Physical
            // Buttons (8 bits)
            HID_RI_USAGE_PAGE(8, 0x09),    // Button
            HID_RI_USAGE_MINIMUM(8, 0x01), // Button 1
            HID_RI_USAGE_MAXIMUM(8, 0x08), // Button 8
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x01),
            HID_RI_REPORT_COUNT(8, 0x08),
            HID_RI_REPORT_SIZE(8, 0x01),
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),

#    ifdef MOUSE_EXTENDED_REPORT
            // Boot protocol XY ignored in Report protocol
            HID_RI_REPORT_COUNT(8, 0x02),
            HID_RI_REPORT_SIZE(8, 0x08),
            HID_RI_INPUT(8, HID_IOF_CONSTANT),
#    endif
            // X/Y position (2 or 4 bytes)
            HID_RI_USAGE_PAGE(8, 0x01),    // Generic Desktop
            HID_RI_USAGE(8, 0x30),         // X
            HID_RI_USAGE(8, 0x31),         // Y
#    ifndef MOUSE_EXTENDED_REPORT
            HID_RI_LOGICAL_MINIMUM(8, -127),
            HID_RI_LOGICAL_MAXIMUM(8, 127),
            HID_RI_REPORT_COUNT(8, 0x02),
            HID_RI_REPORT_SIZE(8, 0x08),
#    else
            HID_RI_LOGICAL_MINIMUM(16, -32767),
            HID_RI_LOGICAL_MAXIMUM(16,  32767),
            HID_RI_REPORT_COUNT(8, 0x02),
            HID_RI_REPORT_SIZE(8, 0x10),
#    endif
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_RELATIVE),

#    ifdef POINTING_DEVICE_HIRES_SCROLL_ENABLE
            HID_RI_COLLECTION(8, 0x02),
            // Feature report and padding (1 byte)
            HID_RI_USAGE(8, 0x48),     // Resolution Multiplier
            HID_RI_REPORT_COUNT(8, 0x01),
            HID_RI_REPORT_SIZE(8, 0x02),
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x01),
            HID_RI_PHYSICAL_MINIMUM(8, 1),
            HID_RI_PHYSICAL_MAXIMUM(8, POINTING_DEVICE_HIRES_SCROLL_MULTIPLIER),
            HID_RI_UNIT_EXPONENT(8, POINTING_DEVICE_HIRES_SCROLL_EXPONENT),
            HID_RI_FEATURE(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
            HID_RI_PHYSICAL_MINIMUM(8, 0x00),
            HID_RI_PHYSICAL_MAXIMUM(8, 0x00),
            HID_RI_REPORT_SIZE(8, 0x06),
            HID_RI_FEATURE(8, HID_IOF_CONSTANT),
#    endif

            // Vertical wheel (1 or 2 bytes)
            HID_RI_USAGE(8, 0x38),     // Wheel
#    ifndef WHEEL_EXTENDED_REPORT
            HID_RI_LOGICAL_MINIMUM(8, -127),
            HID_RI_LOGICAL_MAXIMUM(8, 127),
            HID_RI_REPORT_COUNT(8, 0x01),
            HID_RI_REPORT_SIZE(8, 0x08),
#    else
            HID_RI_LOGICAL_MINIMUM(16, -32767),
            HID_RI_LOGICAL_MAXIMUM(16,  32767),
            HID_RI_REPORT_COUNT(8, 0x01),
            HID_RI_REPORT_SIZE(8, 0x10),
#    endif
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_RELATIVE),

            // Horizontal wheel (1 or 2 bytes)
            HID_RI_USAGE_PAGE(8, 0x0C),// Consumer
            HID_RI_USAGE(16, 0x0238),  // AC Pan
#    ifndef WHEEL_EXTENDED_REPORT
            HID_RI_LOGICAL_MINIMUM(8, -127),
            HID_RI_LOGICAL_MAXIMUM(8, 127),
            HID_RI_REPORT_COUNT(8, 0x01),
            HID_RI_REPORT_SIZE(8, 0x08),
#    else
            HID_RI_LOGICAL_MINIMUM(16, -32767),
            HID_RI_LOGICAL_MAXIMUM(16,  32767),
            HID_RI_REPORT_COUNT(8, 0x01),
            HID_RI_REPORT_SIZE(8, 0x10),
#    endif
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_RELATIVE),

#    ifdef POINTING_DEVICE_HIRES_SCROLL_ENABLE
            HID_RI_END_COLLECTION(0),
#    endif

        HID_RI_END_COLLECTION(0),
    HID_RI_END_COLLECTION(0),
#    ifndef MOUSE_SHARED_EP
};
#    endif
#endif

#ifdef JOYSTICK_ENABLE
#    ifndef JOYSTICK_SHARED_EP
const USB_Descriptor_HIDReport_Datatype_t PROGMEM JoystickReport[] = {
#    elif !defined(SHARED_REPORT_STARTED)
const USB_Descriptor_HIDReport_Datatype_t PROGMEM SharedReport[] = {
#        define SHARED_REPORT_STARTED
#    endif
    HID_RI_USAGE_PAGE(8, 0x01),     // Generic Desktop
    HID_RI_USAGE(8, 0x04),          // Joystick
    HID_RI_COLLECTION(8, 0x01),     // Application
#    ifdef JOYSTICK_SHARED_EP
        HID_RI_REPORT_ID(8, REPORT_ID_JOYSTICK),
#    endif
        HID_RI_COLLECTION(8, 0x00), // Physical
#    if JOYSTICK_AXIS_COUNT > 0
            HID_RI_USAGE_PAGE(8, 0x01), // Generic Desktop
            HID_RI_USAGE(8, 0x30),      // X
#        if JOYSTICK_AXIS_COUNT > 1
            HID_RI_USAGE(8, 0x31),      // Y
#        endif
#        if JOYSTICK_AXIS_COUNT > 2
            HID_RI_USAGE(8, 0x32),      // Z
#        endif
#        if JOYSTICK_AXIS_COUNT > 3
            HID_RI_USAGE(8, 0x33),      // Rx
#        endif
#        if JOYSTICK_AXIS_COUNT > 4
            HID_RI_USAGE(8, 0x34),      // Ry
#        endif
#        if JOYSTICK_AXIS_COUNT > 5
            HID_RI_USAGE(8, 0x35),      // Rz
#        endif
#        if JOYSTICK_AXIS_RESOLUTION == 8
            HID_RI_LOGICAL_MINIMUM(8, -JOYSTICK_MAX_VALUE),
            HID_RI_LOGICAL_MAXIMUM(8, JOYSTICK_MAX_VALUE),
            HID_RI_REPORT_COUNT(8, JOYSTICK_AXIS_COUNT),
            HID_RI_REPORT_SIZE(8, 0x08),
#        else
            HID_RI_LOGICAL_MINIMUM(16, -JOYSTICK_MAX_VALUE),
            HID_RI_LOGICAL_MAXIMUM(16, JOYSTICK_MAX_VALUE),
            HID_RI_REPORT_COUNT(8, JOYSTICK_AXIS_COUNT),
            HID_RI_REPORT_SIZE(8, 0x10),
#        endif
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
#    endif

#    ifdef JOYSTICK_HAS_HAT
            // Hat Switch (4 bits)
            HID_RI_USAGE(8, 0x39), // Hat Switch
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x07),
            HID_RI_PHYSICAL_MINIMUM(8, 0),
            HID_RI_PHYSICAL_MAXIMUM(16, 315),
            HID_RI_UNIT(8, 0x14),  // Degree, English Rotation
            HID_RI_REPORT_COUNT(8, 1),
            HID_RI_REPORT_SIZE(8, 4),
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE | HID_IOF_NULLSTATE),
            // Padding (4 bits)
            HID_RI_REPORT_COUNT(8, 0x04),
            HID_RI_REPORT_SIZE(8, 0x01),
            HID_RI_INPUT(8, HID_IOF_CONSTANT),
#    endif

#    if JOYSTICK_BUTTON_COUNT > 0
            HID_RI_USAGE_PAGE(8, 0x09), // Button
            HID_RI_USAGE_MINIMUM(8, 0x01),
            HID_RI_USAGE_MAXIMUM(8, JOYSTICK_BUTTON_COUNT),
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x01),
            HID_RI_REPORT_COUNT(8, JOYSTICK_BUTTON_COUNT),
            HID_RI_REPORT_SIZE(8, 0x01),
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),

#        if (JOYSTICK_BUTTON_COUNT % 8) != 0
            HID_RI_REPORT_COUNT(8, 8 - (JOYSTICK_BUTTON_COUNT % 8)),
            HID_RI_REPORT_SIZE(8, 0x01),
            HID_RI_INPUT(8, HID_IOF_CONSTANT),
#        endif
#    endif
        HID_RI_END_COLLECTION(0),
    HID_RI_END_COLLECTION(0),
#    ifndef JOYSTICK_SHARED_EP
};
#    endif
#endif

#ifdef DIGITIZER_ENABLE
#    ifndef DIGITIZER_SHARED_EP
const USB_Descriptor_HIDReport_Datatype_t PROGMEM DigitizerReport[] = {
#    elif !defined(SHARED_REPORT_STARTED)
const USB_Descriptor_HIDReport_Datatype_t PROGMEM SharedReport[] = {
#        define SHARED_REPORT_STARTED
#    endif
    HID_RI_USAGE_PAGE(8, 0x0D),            // Digitizers
    HID_RI_USAGE(8, 0x01),                 // Digitizer
    HID_RI_COLLECTION(8, 0x01),            // Application
#    ifdef DIGITIZER_SHARED_EP
        HID_RI_REPORT_ID(8, REPORT_ID_DIGITIZER),
#    endif
        HID_RI_USAGE(8, 0x20),             // Stylus
        HID_RI_COLLECTION(8, 0x00),        // Physical
            // In Range, Tip Switch & Barrel Switch (3 bits)
            HID_RI_USAGE(8, 0x32),         // In Range
            HID_RI_USAGE(8, 0x42),         // Tip Switch
            HID_RI_USAGE(8, 0x44),         // Barrel Switch
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x01),
            HID_RI_REPORT_COUNT(8, 0x03),
            HID_RI_REPORT_SIZE(8, 0x01),
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
            // Padding (5 bits)
            HID_RI_REPORT_COUNT(8, 0x05),
            HID_RI_INPUT(8, HID_IOF_CONSTANT),

            // X/Y Position (4 bytes)
            HID_RI_USAGE_PAGE(8, 0x01),    // Generic Desktop
            HID_RI_USAGE(8, 0x30),         // X
            HID_RI_USAGE(8, 0x31),         // Y
            HID_RI_LOGICAL_MAXIMUM(16, 0x7FFF),
            HID_RI_REPORT_COUNT(8, 0x02),
            HID_RI_REPORT_SIZE(8, 0x10),
            HID_RI_UNIT(8, 0x13),          // Inch, English Linear
            HID_RI_UNIT_EXPONENT(8, 0x0E), // -2
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
        HID_RI_END_COLLECTION(0),
    HID_RI_END_COLLECTION(0),
#    ifndef DIGITIZER_SHARED_EP
};
#    endif
#endif

#if defined(SHARED_EP_ENABLE) && !defined(SHARED_REPORT_STARTED)
const USB_Descriptor_HIDReport_Datatype_t PROGMEM SharedReport[] = {
#endif

#ifdef EXTRAKEY_ENABLE
    HID_RI_USAGE_PAGE(8, 0x01),           // Generic Desktop
    HID_RI_USAGE(8, 0x80),                // System Control
    HID_RI_COLLECTION(8, 0x01),           // Application
        HID_RI_REPORT_ID(8, REPORT_ID_SYSTEM),
        HID_RI_USAGE_MINIMUM(8, 0x01),    // Pointer
        HID_RI_USAGE_MAXIMUM(16, 0x00B7), // System Display LCD Autoscale
        HID_RI_LOGICAL_MINIMUM(8, 0x01),
        HID_RI_LOGICAL_MAXIMUM(16, 0x00B7),
        HID_RI_REPORT_COUNT(8, 1),
        HID_RI_REPORT_SIZE(8, 16),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_ARRAY | HID_IOF_ABSOLUTE),
    HID_RI_END_COLLECTION(0),

    HID_RI_USAGE_PAGE(8, 0x0C),           // Consumer
    HID_RI_USAGE(8, 0x01),                // Consumer Control
    HID_RI_COLLECTION(8, 0x01),           // Application
        HID_RI_REPORT_ID(8, REPORT_ID_CONSUMER),
        HID_RI_USAGE_MINIMUM(8, 0x01),    // Consumer Control
        HID_RI_USAGE_MAXIMUM(16, 0x02A0), // AC Desktop Show All Applications
        HID_RI_LOGICAL_MINIMUM(8, 0x01),
        HID_RI_LOGICAL_MAXIMUM(16, 0x02A0),
        HID_RI_REPORT_COUNT(8, 1),
        HID_RI_REPORT_SIZE(8, 16),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_ARRAY | HID_IOF_ABSOLUTE),
    HID_RI_END_COLLECTION(0),
#endif

#ifdef PROGRAMMABLE_BUTTON_ENABLE
    HID_RI_USAGE_PAGE(8, 0x0C),            // Consumer
    HID_RI_USAGE(8, 0x01),                 // Consumer Control
    HID_RI_COLLECTION(8, 0x01),            // Application
        HID_RI_REPORT_ID(8, REPORT_ID_PROGRAMMABLE_BUTTON),
        HID_RI_USAGE(8, 0x03),             // Programmable Buttons
        HID_RI_COLLECTION(8, 0x04),        // Named Array
            HID_RI_USAGE_PAGE(8, 0x09),    // Button
            HID_RI_USAGE_MINIMUM(8, 0x01), // Button 1
            HID_RI_USAGE_MAXIMUM(8, 0x20), // Button 32
            HID_RI_LOGICAL_MINIMUM(8, 0x00),
            HID_RI_LOGICAL_MAXIMUM(8, 0x01),
            HID_RI_REPORT_COUNT(8, 32),
            HID_RI_REPORT_SIZE(8, 1),
            HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
        HID_RI_END_COLLECTION(0),
    HID_RI_END_COLLECTION(0),
#endif

#ifdef NKRO_ENABLE
    HID_RI_USAGE_PAGE(8, 0x01),        // Generic Desktop
    HID_RI_USAGE(8, 0x06),             // Keyboard
    HID_RI_COLLECTION(8, 0x01),        // Application
        HID_RI_REPORT_ID(8, REPORT_ID_NKRO),
        // Modifiers (8 bits)
        HID_RI_USAGE_PAGE(8, 0x07),    // Keyboard/Keypad
        HID_RI_USAGE_MINIMUM(8, 0xE0), // Keyboard Left Control
        HID_RI_USAGE_MAXIMUM(8, 0xE7), // Keyboard Right GUI
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(8, 0x01),
        HID_RI_REPORT_COUNT(8, 0x08),
        HID_RI_REPORT_SIZE(8, 0x01),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),
        // Keycodes
        HID_RI_USAGE_PAGE(8, 0x07),    // Keyboard/Keypad
        HID_RI_USAGE_MINIMUM(8, 0x00),
        HID_RI_USAGE_MAXIMUM(8, NKRO_REPORT_BITS * 8 - 1),
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(8, 0x01),
        HID_RI_REPORT_COUNT(8, NKRO_REPORT_BITS * 8),
        HID_RI_REPORT_SIZE(8, 0x01),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),

        // Status LEDs (5 bits)
        HID_RI_USAGE_PAGE(8, 0x08),    // LED
        HID_RI_USAGE_MINIMUM(8, 0x01), // Num Lock
        HID_RI_USAGE_MAXIMUM(8, 0x05), // Kana
        HID_RI_REPORT_COUNT(8, 0x05),
        HID_RI_REPORT_SIZE(8, 0x01),
        HID_RI_OUTPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE | HID_IOF_NON_VOLATILE),
        // LED padding (3 bits)
        HID_RI_REPORT_COUNT(8, 0x01),
        HID_RI_REPORT_SIZE(8, 0x03),
        HID_RI_OUTPUT(8, HID_IOF_CONSTANT),
    HID_RI_END_COLLECTION(0),
#endif

#ifdef SHARED_EP_ENABLE
};
#endif

#ifdef RAW_ENABLE
const USB_Descriptor_HIDReport_Datatype_t PROGMEM RawReport[] = {
    HID_RI_USAGE_PAGE(16, RAW_USAGE_PAGE), // Vendor Defined
    HID_RI_USAGE(8, RAW_USAGE_ID),         // Vendor Defined
    HID_RI_COLLECTION(8, 0x01),    // Application
        // Data to host
        HID_RI_USAGE(8, 0x62),     // Vendor Defined
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(16, 0x00FF),
        HID_RI_REPORT_COUNT(8, RAW_EPSIZE),
        HID_RI_REPORT_SIZE(8, 0x08),
        HID_RI_INPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE),

        // Data from host
        HID_RI_USAGE(8, 0x63),     // Vendor Defined
        HID_RI_LOGICAL_MINIMUM(8, 0x00),
        HID_RI_LOGICAL_MAXIMUM(16, 0x00FF),
        HID_RI_REPORT_COUNT(8, RAW_EPSIZE),
        HID_RI_REPORT_SIZE(8, 0x08),
        HID_RI_OUTPUT(8, HID_IOF_DATA | HID_IOF_VARIABLE | HID_IOF_ABSOLUTE | HID_IOF_NON_VOLATILE),
    HID_RI_END_COLLECTION(0),
};
#endif
