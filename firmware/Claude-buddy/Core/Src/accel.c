/**
 * accel.c - Slap detection with the LSM6DSL accelerometer (see accel.h).
 *
 * How a slap is found:
 *   1. Every SAMPLE_MS we read the acceleration on 3 axes, in milli-g.
 *   2. "baseline" is a slow running average of those readings. At rest it is
 *      just gravity (about 1000 mg pointing down, whatever way the board sits).
 *   3. The difference between the new reading and the baseline is the jolt.
 *      If its size is above SLAP_THRESHOLD_MG, that is a slap.
 *   4. Knock-knock: after a tap the board waits KNOCK_WINDOW_END_MS before
 *      reporting it. A second jolt of at least KNOCK_MIN_MG, and at least
 *      KNOCK_MIN_RATIO of the first tap, between KNOCK_WINDOW_START_MS and
 *      KNOCK_WINDOW_END_MS after the first tap = a knock-knock. Otherwise it
 *      was a single tap (slap).
 *      Measured on the toy (Nov 21): a single tap's spring bounce comes back
 *      0.15-0.2 s later at up to 60 % of the tap, then stays under ~900 mg
 *      after 0.25 s. A deliberate second knock 0.25-0.4 s later was
 *      3000-3800 mg. A FAST double tap (second tap at 0.15-0.2 s) looks just
 *      like the spring bounce, so it can't be detected: knock with a beat.
 *      Unsure: a FAST knock-knock puts its second tap 0.1-0.25 s after the
 *      first, where a single tap's spring bounce is. Measured: the bounce is
 *      at most 64 % of the tap (16 single taps), a fast second tap 94-181 %.
 *      So a jolt there of at least MAYBE_RATIO of the first tap = "MAYBE"
 *      (probably a fast knock-knock): the laptop asks before doing anything.
 *   5. After a slap, knock-knock or maybe the head keeps wobbling on the springs for
 *      a while, which would look like more taps, so taps are ignored for
 *      COOLDOWN_MS.
 *
 * Tuning: the laptop log shows "SLAP:<strength>" for each slap. If small
 * bumps (typing, a mug on the desk) trigger it, raise SLAP_THRESHOLD_MG.
 * If a real slap is missed, lower it.
 */
#include "accel.h"
#include "i2c.h"
#include <math.h>

#define LSM6DSL_ADDR     (0x6A << 1)  /* 7-bit address 0x6A, HAL wants it shifted left by 1 */
#define REG_WHO_AM_I     0x0F         /* identity register                                 */
#define WHO_AM_I_VALUE   0x6A         /* what an LSM6DSL answers                            */
#define REG_CTRL1_XL     0x10         /* accelerometer speed and range                      */
#define REG_CTRL3_C      0x12         /* general settings                                   */
#define REG_OUTX_L_XL    0x28         /* first of the 6 output bytes (X low, X high, Y...)  */

#define CTRL1_416HZ_4G   0x68         /* 416 samples per second, range +-4 g               */
#define CTRL3_BDU_INC    0x44         /* BDU: low/high bytes from the same sample;
                                         IF_INC: register address moves on by itself      */
#define MG_PER_LSB       0.122f       /* +-4 g range: one count = 0.122 milli-g            */

#define I2C_TIMEOUT_MS     5          /* give up on a stuck I2C read after 5 ms            */
#define SAMPLE_MS          5          /* read a sample every 5 ms (200 per second)         */
#define SLAP_THRESHOLD_MG  700.0f     /* jolt size that counts as a slap (0.7 g)           */
#define COOLDOWN_MS        1000       /* ignore the wobbling for 1 s after a decision      */
#define FIRST_TAP_MS       100        /* the first tap's own spike lasts this long          */
#define KNOCK_WINDOW_START_MS 250     /* second knock: not before (spring bounce until then) */
#define MAYBE_RATIO        0.80f      /* fast jolt >= 80 % of the tap: maybe a fast knock   */
#define KNOCK_WINDOW_END_MS   800     /* second knock: not after; a single tap is reported then */
#define KNOCK_MIN_MG       1500.0f    /* second knock at least this big (bounce stays < ~900) */
#define KNOCK_MIN_RATIO    0.35f      /* ...and at least 35 % of the first tap              */
#define BASELINE_WEIGHT    0.02f      /* how fast the baseline follows (2 % per sample)    */

static uint8_t  ready;                /* 1 = chip found and set up                          */
static uint8_t  have_baseline;        /* 1 = baseline holds a real reading                  */
static float    base_x, base_y, base_z;  /* resting acceleration (gravity), milli-g         */
static uint32_t last_sample;          /* HAL_GetTick() of the last read                     */
static uint32_t last_event;           /* HAL_GetTick() of the last slap / knock-knock       */
static uint8_t  waiting;              /* 1 = a tap happened, waiting to see if a 2nd follows */
static uint32_t first_tap_at;         /* HAL_GetTick() of that first tap                    */
static float    first_tap_mg;         /* its biggest jolt in the first 0.1 s (milli-g)      */
static float    fast_max_mg;          /* biggest jolt 0.1-0.25 s after it (bounce or 2nd tap) */

/* Write one byte into one register of the chip. Returns 1 on success. */
static uint8_t write_reg(uint8_t reg, uint8_t value)
{
  return HAL_I2C_Mem_Write(&hi2c2, LSM6DSL_ADDR, reg, I2C_MEMADD_SIZE_8BIT,
                           &value, 1, I2C_TIMEOUT_MS) == HAL_OK;
}

/* Read `len` bytes starting at register `reg`. Returns 1 on success. */
static uint8_t read_regs(uint8_t reg, uint8_t *out, uint16_t len)
{
  return HAL_I2C_Mem_Read(&hi2c2, LSM6DSL_ADDR, reg, I2C_MEMADD_SIZE_8BIT,
                          out, len, I2C_TIMEOUT_MS) == HAL_OK;
}

uint8_t Accel_Init(void)
{
  uint8_t id = 0;
  ready = 0;
  if (!read_regs(REG_WHO_AM_I, &id, 1) || id != WHO_AM_I_VALUE) {
    return 0;                                     /* chip missing or not answering   */
  }
  if (!write_reg(REG_CTRL3_C, CTRL3_BDU_INC)) return 0;   /* settings first          */
  if (!write_reg(REG_CTRL1_XL, CTRL1_416HZ_4G)) return 0; /* this starts measuring   */
  have_baseline = 0;                              /* first sample becomes baseline   */
  ready = 1;
  return 1;
}

AccelEvent Accel_Check(uint32_t now, uint16_t *strength_mg)
{
  if (!ready) return ACCEL_NOTHING;               /* no chip: never a slap           */
  if (now - last_sample < SAMPLE_MS) return ACCEL_NOTHING;  /* too soon for a sample */
  last_sample = now;

  uint8_t raw[6];
  if (!read_regs(REG_OUTX_L_XL, raw, 6)) return ACCEL_NOTHING;  /* read failed       */

  /* Each axis is a signed 16-bit number, low byte first. */
  float x = (int16_t)(raw[0] | (raw[1] << 8)) * MG_PER_LSB;
  float y = (int16_t)(raw[2] | (raw[3] << 8)) * MG_PER_LSB;
  float z = (int16_t)(raw[4] | (raw[5] << 8)) * MG_PER_LSB;

  if (!have_baseline) {                           /* very first sample after start   */
    base_x = x; base_y = y; base_z = z;
    have_baseline = 1;
    return ACCEL_NOTHING;
  }

  /* How far this sample is from rest, as one number (length of the difference). */
  float dx = x - base_x, dy = y - base_y, dz = z - base_z;
  float jolt = sqrtf(dx * dx + dy * dy + dz * dz);

  /* Move the baseline a little toward this sample, so it follows slow changes
   * (for example the head settling at a slightly different angle). */
  base_x += (x - base_x) * BASELINE_WEIGHT;
  base_y += (y - base_y) * BASELINE_WEIGHT;
  base_z += (z - base_z) * BASELINE_WEIGHT;

  if (waiting) {
    /* A tap happened: was it the first half of a knock-knock? */
    uint32_t elapsed = now - first_tap_at;
    if (elapsed < FIRST_TAP_MS) {
      /* Still the first tap's spike: remember its biggest jolt. */
      if (jolt > first_tap_mg) first_tap_mg = jolt;
      return ACCEL_NOTHING;
    }
    if (elapsed < KNOCK_WINDOW_START_MS) {
      /* Spring bounce, or a fast second tap: remember the biggest jolt. */
      if (jolt > fast_max_mg) fast_max_mg = jolt;
      return ACCEL_NOTHING;
    }
    if (jolt >= KNOCK_MIN_MG && jolt >= first_tap_mg * KNOCK_MIN_RATIO) {
      waiting = 0;                                /* second knock: knock-knock       */
      last_event = now;
      *strength_mg = jolt > 65535.0f ? 65535 : (uint16_t)jolt;
      return ACCEL_KNOCK;
    }
    if (elapsed > KNOCK_WINDOW_END_MS) {
      waiting = 0;                                /* no clear second knock           */
      last_event = now;
      if (fast_max_mg >= first_tap_mg * MAYBE_RATIO && fast_max_mg >= SLAP_THRESHOLD_MG) {
        /* Too big for a bounce: probably a fast knock-knock. Laptop asks. */
        *strength_mg = fast_max_mg > 65535.0f ? 65535 : (uint16_t)fast_max_mg;
        return ACCEL_MAYBE;
      }
      *strength_mg = first_tap_mg > 65535.0f ? 65535 : (uint16_t)first_tap_mg;
      return ACCEL_SLAP;                          /* a single tap                    */
    }
    return ACCEL_NOTHING;                         /* keep waiting                    */
  }

  if (jolt < SLAP_THRESHOLD_MG) return ACCEL_NOTHING;      /* normal small movement  */
  if (now - last_event < COOLDOWN_MS) return ACCEL_NOTHING; /* still wobbling        */
  waiting = 1;                                    /* a tap: wait for a second one    */
  first_tap_at = now;
  first_tap_mg = jolt;
  fast_max_mg = 0.0f;
  return ACCEL_NOTHING;
}
