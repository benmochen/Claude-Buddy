/**
 * ili9341.h - Minimal ILI9341 driver (2.8" 240x320 SPI TFT) on SPI1.
 *
 * Wiring (TFT module -> B-L4S5I-IOT01A Arduino header):
 *   VCC  -> 5V  (module has its own 3.3 V regulator while J1 is open)
 *   GND  -> GND
 *   CS   -> D10 (PA2)      RESET -> D6 (PB1)     DC -> D7 (PA4)
 *   SDI  -> D11 (PA7)      SCK   -> D13 (PA5)    SDO -> D12 (PA6, for ID read)
 *   LED  -> D3  (PB0, TIM3_CH3 PWM backlight)
 */
#ifndef ILI9341_H
#define ILI9341_H

#include <stdint.h>

/* Landscape: 320 wide x 240 tall. */
#define TFT_W 320
#define TFT_H 240

/* RGB565 helpers. */
#define RGB565(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))
#define COLOR_BLACK         0x0000
#define COLOR_WHITE         0xFFFF
#define COLOR_RED           RGB565(255, 0, 0)
#define COLOR_GREEN         RGB565(0, 255, 0)
#define COLOR_CLAUDE_ORANGE RGB565(0xD9, 0x77, 0x57)

void     TFT_Init(void);
void     TFT_FillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
void     TFT_FillScreen(uint16_t color);

/* Blit a w*h block. Pixels must already be byte-swapped (big-endian RGB565),
 * e.g. via TFT_SWAP(color). w*h*2 must be <= 65535 bytes. */
#define TFT_SWAP(c) ((uint16_t)(((c) >> 8) | ((c) << 8)))
void     TFT_DrawImage(int16_t x, int16_t y, int16_t w, int16_t h, const uint16_t *pixels);

/* Returns 0x9341 on a genuine ILI9341 if SDO/MISO is wired, else garbage/0. */
uint16_t TFT_ReadID(void);

/* Backlight brightness 0..100 %. */
void     TFT_SetBacklight(uint8_t percent);

#endif /* ILI9341_H */
