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

/* What Accel_Check() found. */
typedef enum {
  ACCEL_NOTHING = 0,   /* no new tap (or still waiting to see if a 2nd knock comes) */
  ACCEL_SLAP,          /* one tap                                                   */
  ACCEL_KNOCK,         /* knock-knock: two taps about half a second apart          */
  ACCEL_MAYBE          /* unsure: probably a FAST knock-knock (laptop asks first)  */
} AccelEvent;

/* Call every main-loop pass with HAL_GetTick(). Reads a new sample every few
 * milliseconds. A single tap is reported 0.8 s late (after waiting for a
 * possible second knock). For SLAP / KNOCK, *strength_mg gets the strength in
 * milli-g (1000 = 1 g). */
AccelEvent Accel_Check(uint32_t now, uint16_t *strength_mg);

#endif /* ACCEL_H */
