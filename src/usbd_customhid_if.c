#include "usbd_customhid_if.h"

static int8_t CUSTOM_HID_Init_FS(void);
static int8_t CUSTOM_HID_DeInit_FS(void);
static int8_t CUSTOM_HID_OutEvent_FS(uint8_t event_idx, uint8_t state);

// Generic Desktop -> Multi-axis Controller, two signed 8-bit axes.
__ALIGN_BEGIN static uint8_t CUSTOM_HID_ReportDesc_FS[] __ALIGN_END = {
    0x05, 0x01,       // Usage Page (Generic Desktop)
    0x09, 0x08,       // Usage (Multi-axis Controller)
    0xA1, 0x01,       // Collection (Application)
    0x15, 0x81,       //   Logical Minimum (-127)
    0x25, 0x7F,       //   Logical Maximum (127)
    0x75, 0x08,       //   Report Size (8)
    0x95, 0x02,       //   Report Count (2)
    0x09, 0x30,       //   Usage (X)
    0x09, 0x31,       //   Usage (Y)
    0x81, 0x02,       //   Input (Data,Var,Abs)
    0x95, 0x02,       //   Report Count (2)
    0x09, 0x30,       //   Usage (X)
    0x09, 0x31,       //   Usage (Y)
    0x91, 0x02,       //   Output (Data,Var,Abs)
    0xC0              // End Collection
};

USBD_CUSTOM_HID_ItfTypeDef USBD_CustomHID_fops_FS = {
    CUSTOM_HID_ReportDesc_FS,
    CUSTOM_HID_Init_FS,
    CUSTOM_HID_DeInit_FS,
    CUSTOM_HID_OutEvent_FS
};

static int8_t CUSTOM_HID_Init_FS(void)
{
    return (0);
}

static int8_t CUSTOM_HID_DeInit_FS(void)
{
    return (0);
}

static int8_t CUSTOM_HID_OutEvent_FS(uint8_t event_idx, uint8_t state)
{
    (void)event_idx;
    (void)state;
    return (0);
}
