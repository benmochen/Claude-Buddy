/**
 * lcd1602.h - Minimal HD44780 (LCD1602) driver, 4-bit parallel, write-only.
 *
 * Wiring (B-L4S5I-IOT01A Arduino header -> LCD1602):
 *   LCD RS  <- PA6  (D12)      LCD D4 <- PB4  (D5)
 *   LCD E   <- PA7  (D11)      LCD D5 <- PA3  (D4)
 *   LCD RW  -> GND (always)    LCD D6 <- PB0  (D3)
 *   LCD D0-D3 unconnected      LCD D7 <- PD14 (D2)
 *   VSS -> GND, VDD -> 5V, V0 -> 10k pot wiper (pot ends to 5V/GND),
 *   A -> 5V (via resistor if the module has none), K -> GND.
 *
 * RW must be tied to GND so the 5 V LCD never drives the 3.3 V MCU pins.
 */
#ifndef LCD1602_H
#define LCD1602_H

#include <stdint.h>

#define LCD_COLS 16
#define LCD_ROWS 2

void LCD_Init(void);
void LCD_Clear(void);
void LCD_SetCursor(uint8_t col, uint8_t row);
void LCD_PutChar(uint8_t c);
void LCD_Print(const char *s);

/* Load one 5x8 custom glyph into CGRAM slot 0..7 (rows[0] = top, low 5 bits). */
void LCD_CreateChar(uint8_t slot, const uint8_t rows[8]);

/* Load `count` consecutive glyphs (8 bytes each) starting at `first_slot`. */
void LCD_LoadGlyphs(uint8_t first_slot, const uint8_t *data, uint8_t count);

#endif /* LCD1602_H */
