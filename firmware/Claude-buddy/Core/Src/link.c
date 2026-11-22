/**
 * link.c - Serial protocol with the laptop (see link.h for the messages).
 *
 * Receiving works in two halves:
 *   1. Interrupt: each received byte goes into a ring buffer, then the next
 *      byte is requested. Nothing else happens there, because drawing on the
 *      display inside an interrupt would block the UART for milliseconds.
 *   2. Main loop (Link_Poll): bytes are taken out of the ring buffer and
 *      collected into a line. A full line is then acted on.
 */
#include "link.h"
#include "audio.h"
#include "face.h"
#include "main.h"
#include "usart.h"
#include <stdio.h>
#include <string.h>

#define RX_RING_SIZE 128             /* bytes buffered between interrupt and main loop */
#define LINE_MAX     40              /* longest line we accept (T:<16 chars> fits)     */

static volatile uint8_t  rx_ring[RX_RING_SIZE];  /* bytes written by the interrupt   */
static volatile uint16_t rx_head;                /* where the interrupt writes next  */
static volatile uint16_t rx_tail;                /* where the main loop reads next   */
static uint8_t           rx_byte;                /* HAL receives each byte into here */

static char     line[LINE_MAX + 1];  /* the line being collected, +1 for the '\0' */
static uint16_t line_len;            /* characters in `line` so far              */
static uint8_t  line_too_long;       /* 1 = current line overflowed, drop it     */

/* Ask the HAL to receive one more byte; HAL_UART_RxCpltCallback runs when it arrives. */
static void arm_receive(void)
{
  HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
}

/* Send a whole string. Blocking, but a few bytes at 115200 baud take < 1 ms. */
static void send_text(const char *s)
{
  HAL_UART_Transmit(&huart1, (uint8_t *)s, (uint16_t)strlen(s), 20);
}

/* Act on one complete line (without the '\n'). Unknown lines are ignored. */
static void handle_line(const char *msg)
{
  if (strcmp(msg, "F:IDLE") == 0)       Face_SetMood(FACE_NORMAL);  /* nothing happening   */
  else if (strcmp(msg, "F:WORK") == 0)  Face_SetMood(FACE_NORMAL);  /* Claude working      */
  else if (strcmp(msg, "F:DONE") == 0)  Face_SetMood(FACE_HAPPY);   /* Claude finished     */
  else if (strcmp(msg, "F:NEED") == 0)  Face_SetMood(FACE_SAD);     /* needs permission    */
  else if (strcmp(msg, "F:MAD") == 0)   Face_SetMood(FACE_OUCH);    /* nagging             */
  else if (strcmp(msg, "PING") == 0)    send_text("PONG\n");        /* connection test     */
  else if (strcmp(msg, "S:STOP") == 0)  Audio_Stop();               /* cut the voice off   */
  else if (strncmp(msg, "S:", 2) == 0) {                            /* S:<name> plays a clip */
    if (!Audio_Play(msg + 2)) {
      send_text("ERR:SOUND\n");          /* no clip with that name: laptop logs it */
    }
  }
  /* "T:<text>" and anything else: nothing to show on the TFT yet, ignore. */
}

void Link_Init(void)
{
  rx_head = 0;                       /* empty ring buffer */
  rx_tail = 0;
  line_len = 0;                      /* no partial line yet */
  line_too_long = 0;
  arm_receive();                     /* start listening */
}

void Link_Poll(void)
{
  while (rx_tail != rx_head) {                       /* bytes waiting from the interrupt */
    uint8_t c = rx_ring[rx_tail];                    /* take the oldest byte             */
    rx_tail = (uint16_t)((rx_tail + 1) % RX_RING_SIZE);

    if (c == '\n' || c == '\r') {                    /* end of a line                    */
      if (line_len > 0 && !line_too_long) {          /* skip empty and overflowed lines  */
        line[line_len] = '\0';                       /* make it a C string               */
        handle_line(line);
      }
      line_len = 0;                                  /* start the next line fresh        */
      line_too_long = 0;
    } else if (line_len < LINE_MAX) {
      line[line_len++] = (char)c;                    /* add the character                */
    } else {
      line_too_long = 1;                             /* too long: drop the whole line    */
    }
  }
}

void Link_SendButton(void)
{
  send_text("BTN\n");
}

void Link_SendSlap(uint16_t strength_mg)
{
  char msg[16];                                      /* "SLAP:65535\n" fits      */
  snprintf(msg, sizeof msg, "SLAP:%u\n", (unsigned)strength_mg);
  send_text(msg);
}

void Link_SendKnock(uint16_t strength_mg)
{
  char msg[16];                                      /* "KNOCK:65535\n" fits     */
  snprintf(msg, sizeof msg, "KNOCK:%u\n", (unsigned)strength_mg);
  send_text(msg);
}

void Link_SendMaybe(uint16_t strength_mg)
{
  char msg[16];                                      /* "MAYBE:65535\n" fits     */
  snprintf(msg, sizeof msg, "MAYBE:%u\n", (unsigned)strength_mg);
  send_text(msg);
}

void Link_SendLine(const char *text)
{
  send_text(text);
  send_text("\n");
}

/* ---- HAL callbacks (these replace the empty "weak" versions in the HAL) ---- */

/* Runs inside the USART1 interrupt each time one byte has arrived. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance != USART1) return;             /* not our UART                     */
  uint16_t next = (uint16_t)((rx_head + 1) % RX_RING_SIZE);
  if (next != rx_tail) {                             /* room left? (else drop the byte)  */
    rx_ring[rx_head] = rx_byte;
    rx_head = next;
  }
  arm_receive();                                     /* ask for the next byte            */
}

/* Runs on a receive error (for example an overrun when bytes came too fast).
 * The HAL stops receiving after an error, so start again. */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance != USART1) return;
  arm_receive();
}
