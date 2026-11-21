/**
 * link.h - Text protocol between the laptop and the board over USART1
 * (the ST-LINK virtual COM port, 115200 8N1). Every message is one line
 * ending in '\n'.
 *
 * Laptop -> board:
 *   F:IDLE   face normal      (nothing happening)
 *   F:WORK   face normal      (Claude is working)
 *   F:DONE   face happy ^ ^   (Claude finished)
 *   F:NEED   face sad /. .\   (Claude needs permission)
 *   F:MAD    face ouch > <    (you ignored it, nagging)
 *   T:<text> status text, accepted but not shown yet (no text on the TFT)
 *   PING     board answers PONG (for testing the cable and port)
 *
 * Board -> laptop:
 *   BTN      the big undo button was pressed
 *   PONG     answer to PING
 */
#ifndef LINK_H
#define LINK_H

/* Start receiving. Call once after MX_USART1_UART_Init(). */
void Link_Init(void);

/* Handle any complete lines received so far. Call every main-loop pass. */
void Link_Poll(void);

/* Tell the laptop the undo button was pressed. */
void Link_SendButton(void);

#endif /* LINK_H */
