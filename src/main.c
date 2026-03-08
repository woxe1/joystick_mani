#include "stm32f1xx_hal.h"
#include "usb_device.h"
#include "usbd_customhid.h"

extern USBD_HandleTypeDef hUsbDeviceFS;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ADC1_Init(void);
static uint16_t ADC_ReadChannel(uint32_t channel);
static void ADC_CalibrateCenter(void);

typedef struct AxisCal
{
    int32_t center;
    int32_t filtered;
} AxisCal;

static int8_t Axis_UpdateAndMap(uint16_t adc, AxisCal *axis);

static ADC_HandleTypeDef hadc1;
static AxisCal axis_x = {2048, 0};
static AxisCal axis_y = {2048, 0};

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_ADC1_Init();
    ADC_CalibrateCenter(); // keep joystick centered during power-up
    MX_USB_DEVICE_Init();

    uint8_t report[2];

    while (1)
    {
        int8_t x = Axis_UpdateAndMap(ADC_ReadChannel(ADC_CHANNEL_0), &axis_x); // PA0 (VRx)
        int8_t y = Axis_UpdateAndMap(ADC_ReadChannel(ADC_CHANNEL_1), &axis_y); // PA1 (VRy)

        report[0] = (uint8_t)x;
        report[1] = (uint8_t)y;

        USBD_CUSTOM_HID_SendReport(&hUsbDeviceFS, report, sizeof(report));
        HAL_Delay(10);
    }
}

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;

    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        // Fallback for boards with broken/missing HSE
        RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
        RCC_OscInitStruct.HSEState = RCC_HSE_OFF;
        RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI_DIV2;
        RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL12;

        if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
        {
            while (1) {}
        }
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
    {
        while (1) {}
    }

    __HAL_RCC_USB_CLK_ENABLE();
}

static void MX_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_0 | GPIO_PIN_1;
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = GPIO_PIN_13;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
}

static void MX_ADC1_Init(void)
{
    __HAL_RCC_ADC1_CLK_ENABLE();

    hadc1.Instance = ADC1;
    hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1;

    if (HAL_ADC_Init(&hadc1) != HAL_OK)
    {
        while (1) {}
    }

    if (HAL_ADCEx_Calibration_Start(&hadc1) != HAL_OK)
    {
        while (1) {}
    }
}

static uint16_t ADC_ReadChannel(uint32_t channel)
{
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel = channel;
    sConfig.Rank = ADC_REGULAR_RANK_1;
    sConfig.SamplingTime = ADC_SAMPLETIME_55CYCLES_5;

    if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
    {
        return 2048;
    }
    if (HAL_ADC_Start(&hadc1) != HAL_OK)
    {
        return 2048;
    }
    if (HAL_ADC_PollForConversion(&hadc1, 10) != HAL_OK)
    {
        HAL_ADC_Stop(&hadc1);
        return 2048;
    }

    uint16_t value = (uint16_t)HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return value;
}

static void ADC_CalibrateCenter(void)
{
    uint32_t sx = 0;
    uint32_t sy = 0;

    for (uint32_t i = 0; i < 64; i++)
    {
        sx += ADC_ReadChannel(ADC_CHANNEL_0);
        sy += ADC_ReadChannel(ADC_CHANNEL_1);
        HAL_Delay(2);
    }

    axis_x.center = (int32_t)(sx / 64U);
    axis_y.center = (int32_t)(sy / 64U);
    axis_x.filtered = 0;
    axis_y.filtered = 0;
}

static int8_t Axis_UpdateAndMap(uint16_t adc, AxisCal *axis)
{
    const int32_t deadzone = 170;
    const int32_t full_scale = 1450; // approx counts from center to edge for full-speed output
    int32_t delta = (int32_t)adc - axis->center;

    // 1st-order low-pass to suppress ADC/pot noise.
    axis->filtered = (axis->filtered * 7 + delta) / 8;
    int32_t f = axis->filtered;
    int32_t absf = (f >= 0) ? f : -f;

    if (absf < deadzone)
    {
        return 0;
    }

    int32_t mapped = (f * 127) / full_scale;

    if (mapped > 127)
    {
        mapped = 127;
    }
    else if (mapped < -127)
    {
        mapped = -127;
    }

    return (int8_t)mapped;
}

void SysTick_Handler(void)
{
    HAL_IncTick();
}
