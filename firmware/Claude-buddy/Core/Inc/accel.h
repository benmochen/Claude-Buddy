/**
 * accel.h - Slap detection with the board's built-in accelerometer
 * (LSM6DSL chip on I2C2, pins PB10 = SCL, PB11 = SDA, address 0x6A).
 *
 * The board is mounted in the head, which sits on springs. A slap makes
 * the head jump, so the measured acceleration moves far away from its
 * resting value (gravity only) for a moment. That jump is a "slap".
 */
#ifndef ACCEL_H
#define ACCEL_H

#include <stdint.h>

/* Checks the chip is there and starts measuring.
 * Returns 1 if the accelerometer answered, 0 if not (slaps then never fire). */
uint8_t Accel_Init(void);

/* Call every main-loop pass with HAL_GetTick(). Reads a new sample every few
 * milliseconds. Returns the strength of a new slap in milli-g (1000 = 1 g),
 * or 0 if there was no new slap. */
uint16_t Accel_CheckSlap(uint32_t now);

#endif /* ACCEL_H */
