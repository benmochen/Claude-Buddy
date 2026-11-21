/**
 * lcd1602.c - HD44780 driver, 4-bit mode, RW grounded (no busy-flag reads,
 * so every command is followed by a fixed worst-case delay).
 */
#include "lcd1602.h"
#include "main.h"

/* HD44780 commands */
#define CMD_CLEAR        0x01
#define CMD_ENTRY_MODE   0x04
#define CMD_DISPLAY_CTRL 0x08
#define CMD_FUNCTION_SET 0x20
#define CMD_SET_CGRAM    0x40
#define CMD_SET_DDRAM    0x80

#define ENTRY_INCREMENT  0x02
#define DISPLAY_ON       0x04
#define FUNC_2LINE       0x08

/* ---------- microsecond delay via the Cortex-M4 cycle counter ---------- */

static void delay_init(void)
{
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CYCCNT = 0;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static void delay_us(uint32_t us)
{
  uint32_t start = DWT->CYCCNT;
  uint32_t ticks = us * (SystemCoreClock / 1000000U);
  while ((DWT->CYCCNT - start) < ticks) { }
}

/* ---------- low level ---------- */

static void write_nibble(uint8_t nib)
{
  HAL_GPIO_WritePin(LCD_D4_GPIO_Port, LCD_D4_Pin, (nib & 0x1) ? GPIO_PIN_SET : GPIO_PIN_RESET);
  HAL_GPIO_WritePin(LCD_D5_GPIO_Port, LCD_D5_Pin, (nib & 0x2) ? GPIO_PIN_SET : GPIO_PIN_RESET);
  HAL_GPIO_WritePin(LCD_D6_GPIO_Port, LCD_D6_Pin, (nib & 0x4) ? GPIO_PIN_SET : GPIO_PIN_RESET);
  HAL_GPIO_WritePin(LCD_D7_GPIO_Port, LCD_D7_Pin, (nib & 0x8) ? GPIO_PIN_SET : GPIO_PIN_RESET);

  delay_us(1);                                   /* address/data setup  */
  HAL_GPIO_WritePin(LCD_E_GPIO_Port, LCD_E_Pin, GPIO_PIN_SET);
  delay_us(1);                                   /* E pulse >= 450 ns   */
  HAL_GPIO_WritePin(LCD_E_GPIO_Port, LCD_E_Pin, GPIO_PIN_RESET);
  delay_us(1);                                   /* hold                */
}

static void write_byte(uint8_t value, uint8_t is_data)
{
  HAL_GPIO_WritePin(LCD_RS_GPIO_Port, LCD_RS_Pin, is_data ? GPIO_PIN_SET : GPIO_PIN_RESET);
  write_nibble(value >> 4);
  write_nibble(value & 0x0F);
  delay_us(50);                                  /* typ. exec time 37 us */
}

static void command(uint8_t cmd) { write_byte(cmd, 0); }

/* ---------- public API ---------- */

void LCD_Init(void)
{
  delay_init();

  HAL_GPIO_WritePin(LCD_RS_GPIO_Port, LCD_RS_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(LCD_E_GPIO_Port, LCD_E_Pin, GPIO_PIN_RESET);

  HAL_Delay(50);                 /* > 40 ms after VDD reaches 4.5 V */

  /* Reset-by-instruction sequence, forces 8-bit, then switches to 4-bit. */
  HAL_GPIO_WritePin(LCD_RS_GPIO_Port, LCD_RS_Pin, GPIO_PIN_RESET);
  write_nibble(0x3); HAL_Delay(5);
  write_nibble(0x3); delay_us(150);
  write_nibble(0x3); delay_us(150);
  write_nibble(0x2); delay_us(150);

  command(CMD_FUNCTION_SET | FUNC_2LINE);        /* 4-bit, 2 lines, 5x8 */
  command(CMD_DISPLAY_CTRL);                     /* display off         */
  LCD_Clear();
  command(CMD_ENTRY_MODE | ENTRY_INCREMENT);     /* cursor moves right  */
  command(CMD_DISPLAY_CTRL | DISPLAY_ON);        /* on, no cursor/blink */
}

void LCD_Clear(void)
{
  command(CMD_CLEAR);
  HAL_Delay(2);                  /* clear takes ~1.52 ms */
}

void LCD_SetCursor(uint8_t col, uint8_t row)
{
  static const uint8_t row_addr[LCD_ROWS] = { 0x00, 0x40 };
  if (row >= LCD_ROWS) row = LCD_ROWS - 1;
  if (col >= LCD_COLS) col = LCD_COLS - 1;
  command(CMD_SET_DDRAM | (row_addr[row] + col));
}

void LCD_PutChar(uint8_t c)
{
  write_byte(c, 1);
}

void LCD_Print(const char *s)
{
  while (*s) LCD_PutChar((uint8_t)*s++);
}

void LCD_CreateChar(uint8_t slot, const uint8_t rows[8])
{
  LCD_LoadGlyphs(slot, rows, 1);
}

void LCD_LoadGlyphs(uint8_t first_slot, const uint8_t *data, uint8_t count)
{
  first_slot &= 0x7;
  if (first_slot + count > 8) count = 8 - first_slot;

  command(CMD_SET_CGRAM | (first_slot << 3));
  for (uint16_t i = 0; i < (uint16_t)count * 8U; i++) {
    LCD_PutChar(data[i] & 0x1F);
  }
  /* Leave the address counter pointing at DDRAM so later prints are sane. */
  command(CMD_SET_DDRAM);
}
