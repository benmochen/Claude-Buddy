/**
 * ili9341.c - Minimal blocking ILI9341 driver over SPI1 (8-bit, mode 0).
 */
#include "ili9341.h"
#include "main.h"
#include "spi.h"
#include "tim.h"

/* MADCTL bits */
#define MADCTL_MY  0x80
#define MADCTL_MX  0x40
#define MADCTL_MV  0x20
#define MADCTL_BGR 0x08

/* Landscape. To rotate the picture 180 degrees, toggle both MADCTL_MX and
 * MADCTL_MY. To mirror it, toggle just one of them. */
#define TFT_MADCTL (MADCTL_MV | MADCTL_BGR)

#define CS_LOW()   HAL_GPIO_WritePin(TFT_CS_GPIO_Port, TFT_CS_Pin, GPIO_PIN_RESET)
#define CS_HIGH()  HAL_GPIO_WritePin(TFT_CS_GPIO_Port, TFT_CS_Pin, GPIO_PIN_SET)
#define DC_CMD()   HAL_GPIO_WritePin(TFT_DC_GPIO_Port, TFT_DC_Pin, GPIO_PIN_RESET)
#define DC_DATA()  HAL_GPIO_WritePin(TFT_DC_GPIO_Port, TFT_DC_Pin, GPIO_PIN_SET)

static void spi_write(const uint8_t *buf, uint16_t len)
{
  HAL_SPI_Transmit(&hspi1, (uint8_t *)buf, len, HAL_MAX_DELAY);
}

static void write_cmd(uint8_t cmd, const uint8_t *data, uint16_t len)
{
  CS_LOW();
  DC_CMD();
  spi_write(&cmd, 1);
  if (len) {
    DC_DATA();
    spi_write(data, len);
  }
  CS_HIGH();
}

#define CMD(c, ...) do { static const uint8_t d_[] = { __VA_ARGS__ }; \
                         write_cmd((c), d_, sizeof d_); } while (0)
#define CMD0(c)     write_cmd((c), 0, 0)

void TFT_Init(void)
{
  /* Hardware reset */
  CS_HIGH();
  HAL_GPIO_WritePin(TFT_RST_GPIO_Port, TFT_RST_Pin, GPIO_PIN_RESET);
  HAL_Delay(10);
  HAL_GPIO_WritePin(TFT_RST_GPIO_Port, TFT_RST_Pin, GPIO_PIN_SET);
  HAL_Delay(120);

  CMD0(0x01);                                  /* software reset        */
  HAL_Delay(150);

  CMD(0xCF, 0x00, 0xC1, 0x30);                 /* power control B       */
  CMD(0xED, 0x64, 0x03, 0x12, 0x81);           /* power on sequence     */
  CMD(0xE8, 0x85, 0x00, 0x78);                 /* driver timing A       */
  CMD(0xCB, 0x39, 0x2C, 0x00, 0x34, 0x02);     /* power control A       */
  CMD(0xF7, 0x20);                             /* pump ratio            */
  CMD(0xEA, 0x00, 0x00);                       /* driver timing B       */
  CMD(0xC0, 0x23);                             /* power control 1       */
  CMD(0xC1, 0x10);                             /* power control 2       */
  CMD(0xC5, 0x3E, 0x28);                       /* VCOM 1                */
  CMD(0xC7, 0x86);                             /* VCOM 2                */
  CMD(0x36, TFT_MADCTL);                       /* orientation           */
  CMD(0x3A, 0x55);                             /* 16-bit pixels         */
  CMD(0xB1, 0x00, 0x18);                       /* frame rate 79 Hz      */
  CMD(0xB6, 0x08, 0x82, 0x27);                 /* display function      */
  CMD(0xF2, 0x00);                             /* 3-gamma off           */
  CMD(0x26, 0x01);                             /* gamma curve 1         */
  CMD(0xE0, 0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
            0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00);
  CMD(0xE1, 0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
            0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F);
  CMD0(0x11);                                  /* sleep out             */
  HAL_Delay(120);
  CMD0(0x29);                                  /* display on            */
}

static void set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1)
{
  uint8_t ca[4] = { x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF };
  uint8_t pa[4] = { y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF };
  write_cmd(0x2A, ca, 4);
  write_cmd(0x2B, pa, 4);
}

void TFT_FillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color)
{
  if (x < 0) { w += x; x = 0; }
  if (y < 0) { h += y; y = 0; }
  if (x + w > TFT_W) w = TFT_W - x;
  if (y + h > TFT_H) h = TFT_H - y;
  if (w <= 0 || h <= 0) return;

  set_window(x, y, x + w - 1, y + h - 1);

  static uint8_t line[TFT_W * 2];
  for (int16_t i = 0; i < w; i++) {
    line[2 * i]     = color >> 8;
    line[2 * i + 1] = color & 0xFF;
  }

  uint8_t cmd = 0x2C;                          /* memory write */
  CS_LOW();
  DC_CMD();
  spi_write(&cmd, 1);
  DC_DATA();
  for (int16_t row = 0; row < h; row++) spi_write(line, (uint16_t)(w * 2));
  CS_HIGH();
}

void TFT_DrawImage(int16_t x, int16_t y, int16_t w, int16_t h, const uint16_t *pixels)
{
  if (w <= 0 || h <= 0 || x < 0 || y < 0 || x + w > TFT_W || y + h > TFT_H) return;
  set_window(x, y, x + w - 1, y + h - 1);

  uint8_t cmd = 0x2C;
  CS_LOW();
  DC_CMD();
  spi_write(&cmd, 1);
  DC_DATA();
  spi_write((const uint8_t *)pixels, (uint16_t)(w * h * 2));
  CS_HIGH();
}

void TFT_FillScreen(uint16_t color)
{
  TFT_FillRect(0, 0, TFT_W, TFT_H, color);
}

/* Reads the ID through the undocumented 0xD9 index register, which is how
 * 4-wire SPI ILI9341 modules expose RDID4 (0xD3). Reads must be slow. */
static uint8_t read_reg8(uint8_t cmd, uint8_t index)
{
  uint8_t idx = 0x10 + index, val = 0;
  write_cmd(0xD9, &idx, 1);

  CS_LOW();
  DC_CMD();
  spi_write(&cmd, 1);
  DC_DATA();
  HAL_SPI_Receive(&hspi1, &val, 1, 10);
  CS_HIGH();
  return val;
}

void TFT_SetBacklight(uint8_t percent)
{
  static uint8_t started;
  if (percent > 100) percent = 100;
  uint32_t period = __HAL_TIM_GET_AUTORELOAD(&htim3) + 1;
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_3, period * percent / 100);
  if (!started) {
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_3);
    started = 1;
  }
}

uint16_t TFT_ReadID(void)
{
  /* Drop SPI clock to 120 MHz / 32 = 3.75 MHz for reads. */
  uint32_t saved = hspi1.Instance->CR1 & SPI_CR1_BR;
  __HAL_SPI_DISABLE(&hspi1);
  MODIFY_REG(hspi1.Instance->CR1, SPI_CR1_BR, SPI_BAUDRATEPRESCALER_32);

  uint16_t id = ((uint16_t)read_reg8(0xD3, 2) << 8) | read_reg8(0xD3, 3);

  __HAL_SPI_DISABLE(&hspi1);
  MODIFY_REG(hspi1.Instance->CR1, SPI_CR1_BR, saved);
  return id;
}
