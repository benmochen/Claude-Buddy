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
 *   S:<name> play voice clip <name> (yay, done, beep, ...) through the DAC on D7
 *   S:STOP   stop the voice clip
 *
 * Board -> laptop:
 *   BTN      the big undo button was pressed
 *   SLAP:<n> the head was slapped, n = strength in milli-g (1000 = 1 g)
 *   ERR:ACCEL the accelerometer did not answer at startup (no slaps)
 *   ERR:SOUND an S:<name> asked for a clip that isn't in audio_clips.c
 *   PONG     answer to PING
 */
#ifndef LINK_H
#define LINK_H

#include <stdint.h>

/* Start receiving. Call once after MX_USART1_UART_Init(). */
void Link_Init(void);

/* Handle any complete lines received so far. Call every main-loop pass. */
void Link_Poll(void);

/* Tell the laptop the undo button was pressed. */
void Link_SendButton(void);

/* Tell the laptop the head was slapped, with its strength in milli-g. */
void Link_SendSlap(uint16_t strength_mg);

/* Tell the laptop the head was knocked twice: sends "KNOCK:<strength_mg>". */
void Link_SendKnock(uint16_t strength_mg);

/* Tell the laptop it's unsure (probably a fast knock-knock): "MAYBE:<strength_mg>". */
void Link_SendMaybe(uint16_t strength_mg);

/* Send one line of text as it is (a '\n' is added). */
void Link_SendLine(const char *text);

#endif /* LINK_H */
