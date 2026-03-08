#include "usb_device.h"
#include "usbd_core.h"
#include "usbd_desc.h"
#include "usbd_customhid.h"
#include "usbd_customhid_if.h"

USBD_HandleTypeDef hUsbDeviceFS;

void MX_USB_DEVICE_Init(void)
{
    USBD_Init(&hUsbDeviceFS, &USBD_Desc, 0);
    USBD_RegisterClass(&hUsbDeviceFS, &USBD_CUSTOM_HID);
    USBD_CUSTOM_HID_RegisterInterface(&hUsbDeviceFS, &USBD_CustomHID_fops_FS);
    USBD_Start(&hUsbDeviceFS);
}
