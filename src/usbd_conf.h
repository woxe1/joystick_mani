#ifndef USBD_CONF_H
#define USBD_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f1xx.h"
#include <stdlib.h>
#include <string.h>

#define USBD_MAX_NUM_INTERFACES          1U
#define USBD_MAX_NUM_CONFIGURATION       1U
#define USBD_MAX_STR_DESC_SIZ            0x100U
#define USBD_SUPPORT_USER_STRING_DESC    0U
#define USBD_SELF_POWERED                0U
#define USBD_DEBUG_LEVEL                 0U

#define USBD_CUSTOMHID_OUTREPORT_BUF_SIZE  2U
#define USBD_CUSTOM_HID_REPORT_DESC_SIZE   29U

#define USBD_malloc         malloc
#define USBD_free           free
#define USBD_memset         memset
#define USBD_memcpy         memcpy

#if (USBD_DEBUG_LEVEL > 0U)
#define USBD_UsrLog(...) do {} while (0)
#else
#define USBD_UsrLog(...) do {} while (0)
#endif
#if (USBD_DEBUG_LEVEL > 1U)
#define USBD_ErrLog(...) do {} while (0)
#else
#define USBD_ErrLog(...) do {} while (0)
#endif
#if (USBD_DEBUG_LEVEL > 2U)
#define USBD_DbgLog(...) do {} while (0)
#else
#define USBD_DbgLog(...) do {} while (0)
#endif

#ifdef __cplusplus
}
#endif

#endif
