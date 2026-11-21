/**
 * accel.c - Slap detection with the LSM6DSL accelerometer (see accel.h).
 *
 * How a slap is found:
 *   1. Every SAMPLE_MS we read the acceleration on 3 axes, in milli-g.
 *   2. "baseline" is a slow running average of those readings. At rest it is
 *      just gravity (about 1000 mg pointing down, whatever way the board sits).
 *   3. The difference between the new reading and the baseline is the jolt.
 *      If its size is above SLAP_THRESHOLD_MG, that is a slap.
 *   4. After a slap the head keeps wobbling on the springs for a while, which
 *      would look like more slaps, so further slaps are ignored for COOLDOWN_MS.
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
#define COOLDOWN_MS        1500       /* ignore the wobbling for 1.5 s after a slap        */
#define BASELINE_WEIGHT    0.02f      /* how fast the baseline follows (2 % per sample)    */

static uint8_t  ready;                /* 1 = chip found and set up                          */
static uint8_t  have_baseline;        /* 1 = baseline holds a real reading                  */
static float    base_x, base_y, base_z;  /* resting acceleration (gravity), milli-g         */
static uint32_t last_sample;          /* HAL_GetTick() of the last read                     */
static uint32_t last_slap;            /* HAL_GetTick() of the last slap                     */

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

uint16_t Accel_CheckSlap(uint32_t now)
{
  if (!ready) return 0;                           /* no chip: never a slap           */
  if (now - last_sample < SAMPLE_MS) return 0;    /* too soon for a new sample       */
  last_sample = now;

  uint8_t raw[6];
  if (!read_regs(REG_OUTX_L_XL, raw, 6)) return 0;   /* read failed: try next time  */

  /* Each axis is a signed 16-bit number, low byte first. */
  float x = (int16_t)(raw[0] | (raw[1] << 8)) * MG_PER_LSB;
  float y = (int16_t)(raw[2] | (raw[3] << 8)) * MG_PER_LSB;
  float z = (int16_t)(raw[4] | (raw[5] << 8)) * MG_PER_LSB;

  if (!have_baseline) {                           /* very first sample after start   */
    base_x = x; base_y = y; base_z = z;
    have_baseline = 1;
    return 0;
  }

  /* How far this sample is from rest, as one number (length of the difference). */
  float dx = x - base_x, dy = y - base_y, dz = z - base_z;
  float jolt = sqrtf(dx * dx + dy * dy + dz * dz);

  /* Move the baseline a little toward this sample, so it follows slow changes
   * (for example the head settling at a slightly different angle). */
  base_x += (x - base_x) * BASELINE_WEIGHT;
  base_y += (y - base_y) * BASELINE_WEIGHT;
  base_z += (z - base_z) * BASELINE_WEIGHT;

  if (jolt < SLAP_THRESHOLD_MG) return 0;         /* normal small movement           */
  if (now - last_slap < COOLDOWN_MS) return 0;    /* still wobbling from last slap   */
  last_slap = now;
  return jolt > 65535.0f ? 65535 : (uint16_t)jolt;  /* report the strength           */
}
