/**
 * face.c - Procedural eye animation for Claude Buddy on an LCD1602.
 *
 * Every frame each eye is drawn into a 10x16 1-bit bitmap from a small
 * "pose" (shape, offset, size). If the bitmap changed, it is sliced into four
 * 5x8 glyphs and pushed to CGRAM. The DDRAM (which cell shows which glyph) is
 * written once at init, so updating CGRAM animates the eyes in place.
 */
#include "face.h"
#include "lcd1602.h"
#include "main.h"
#include <string.h>

/* ---------------- layout (edit to taste) ---------------- */
#define LEFT_EYE_COL    2        /* eye occupies this col and the next */
#define RIGHT_EYE_COL   12
#define BAR_COL_START   6        /* inclusive */
#define BAR_COL_END     9        /* inclusive */
#define FACE_BAR_CHAR   0xFF     /* 0xFF = solid block; use ' ' if the bar is a physical piece */

/* ---------------- timing ---------------- */
#define FRAME_MS        40       /* ~25 fps */
#define DONE_HOLD_MS    3000
#define UNDO_SHOCK_MS   400
#define UNDO_SQUEEZE_MS 1800
#define UNDO_DAZED_MS   2500

/* ---------------- eye geometry ---------------- */
#define EYE_W           10
#define EYE_H           16
#define EYE_OPEN_W      4
#define EYE_OPEN_H      12

typedef struct { uint16_t row[EYE_H]; } EyeBitmap;   /* bit (EYE_W-1-x) = pixel x */

typedef enum { SHAPE_OPEN, SHAPE_HAPPY, SHAPE_CHEVRON } EyeShape;

typedef struct {
  EyeShape shape;
  int8_t   dx, dy;   /* look offset in pixels */
  uint8_t  w, h;     /* size for SHAPE_OPEN   */
} EyePose;

/* ---------------- state ---------------- */
static FaceMood  s_mood;
static uint32_t  s_mood_t0;
static uint32_t  s_last_frame;

static uint8_t   s_blinking;
static uint32_t  s_blink_t0;
static uint32_t  s_next_blink;

static int8_t    s_look_x;
static int8_t    s_look_target;
static uint32_t  s_next_glance;

static EyeBitmap s_last[2];
static uint8_t   s_force_redraw;

static uint32_t  s_rng = 0x1234567u;

static uint32_t rnd(void)
{
  s_rng ^= s_rng << 13;
  s_rng ^= s_rng >> 17;
  s_rng ^= s_rng << 5;
  return s_rng;
}

/* ---------------- bitmap drawing ---------------- */

static void px(EyeBitmap *b, int x, int y, uint8_t mirror)
{
  if (mirror) x = EYE_W - 1 - x;
  if (x < 0 || x >= EYE_W || y < 0 || y >= EYE_H) return;
  b->row[y] |= (uint16_t)(1u << (EYE_W - 1 - x));
}

static void draw_open(EyeBitmap *b, const EyePose *p)
{
  int x0 = (EYE_W - p->w) / 2 + p->dx;
  int y0 = (EYE_H - p->h) / 2 + p->dy;
  uint8_t round = (p->w >= 4 && p->h >= 4);

  for (int y = 0; y < p->h; y++) {
    for (int x = 0; x < p->w; x++) {
      uint8_t corner = (x == 0 || x == p->w - 1) && (y == 0 || y == p->h - 1);
      if (round && corner) continue;
      px(b, x0 + x, y0 + y, 0);
    }
  }
}

/* "^" shape, two pixels thick. */
static void draw_happy(EyeBitmap *b, const EyePose *p)
{
  for (int i = 0; i < 8; i++) {
    int up = (i < 4) ? i : 7 - i;
    int x  = 1 + i + p->dx;
    int y  = 9 - up + p->dy;
    px(b, x, y, 0);
    px(b, x, y + 1, 0);
  }
}

/* ">" for the left eye; mirrored to "<" for the right eye. */
static void draw_chevron(EyeBitmap *b, const EyePose *p, uint8_t mirror)
{
  for (int k = 0; k < 6; k++) {
    int x = 2 + k + (mirror ? -p->dx : p->dx);
    px(b, x,     3 + k  + p->dy, mirror);
    px(b, x + 1, 3 + k  + p->dy, mirror);
    px(b, x,     13 - k + p->dy, mirror);
    px(b, x + 1, 13 - k + p->dy, mirror);
  }
}

/* ---------------- rendering ---------------- */

static void render_eye(uint8_t idx, const EyePose *p)
{
  EyeBitmap bm;
  memset(&bm, 0, sizeof bm);

  switch (p->shape) {
    case SHAPE_OPEN:    draw_open(&bm, p);           break;
    case SHAPE_HAPPY:   draw_happy(&bm, p);          break;
    case SHAPE_CHEVRON: draw_chevron(&bm, p, idx);   break;
  }

  if (!s_force_redraw && memcmp(&bm, &s_last[idx], sizeof bm) == 0) return;
  s_last[idx] = bm;

  /* Slice into 4 glyphs: [top-left, top-right, bottom-left, bottom-right]. */
  uint8_t glyphs[4 * 8];
  for (uint8_t cell = 0; cell < 4; cell++) {
    uint8_t cx = cell & 1, cy = cell >> 1;
    for (uint8_t r = 0; r < 8; r++) {
      glyphs[cell * 8 + r] = (uint8_t)((bm.row[cy * 8 + r] >> (5 * (1 - cx))) & 0x1F);
    }
  }
  LCD_LoadGlyphs(idx * 4, glyphs, 4);
}

static void draw_layout(void)
{
  LCD_Clear();
  for (uint8_t row = 0; row < 2; row++) {
    LCD_SetCursor(LEFT_EYE_COL, row);
    LCD_PutChar(row * 2 + 0);
    LCD_PutChar(row * 2 + 1);

    LCD_SetCursor(RIGHT_EYE_COL, row);
    LCD_PutChar(4 + row * 2 + 0);
    LCD_PutChar(4 + row * 2 + 1);

    LCD_SetCursor(BAR_COL_START, row);
    for (uint8_t c = BAR_COL_START; c <= BAR_COL_END; c++) LCD_PutChar(FACE_BAR_CHAR);
  }
}

/* ---------------- behaviours ---------------- */

static uint8_t blink_height(uint32_t now, uint8_t full_h)
{
  if (!s_blinking && (int32_t)(now - s_next_blink) >= 0) {
    s_blinking   = 1;
    s_blink_t0   = now;
    s_next_blink = now + 2000 + rnd() % 3500;
  }
  if (!s_blinking) return full_h;

  uint32_t t = now - s_blink_t0;
  if (t < 50)  return full_h / 2;
  if (t < 110) return 1;
  if (t < 160) return full_h / 2;
  s_blinking = 0;
  return full_h;
}

void Face_SetMood(FaceMood mood)
{
  uint32_t now = HAL_GetTick();
  s_mood          = mood;
  s_mood_t0       = now;
  s_blinking      = 0;
  s_look_target   = 0;
  s_next_blink    = now + 800 + rnd() % 2000;
  s_next_glance   = now + 1500;
}

FaceMood Face_GetMood(void) { return s_mood; }

void Face_Init(void)
{
  s_rng ^= HAL_GetTick() * 2654435761u;
  if (s_rng == 0) s_rng = 1;

  draw_layout();
  s_look_x = 0;
  s_force_redraw = 1;
  Face_SetMood(FACE_IDLE);
  s_last_frame = HAL_GetTick() - FRAME_MS;
  Face_Update(HAL_GetTick());
}

void Face_Update(uint32_t now)
{
  if (now - s_last_frame < FRAME_MS) return;
  s_last_frame = now;

  uint32_t t = now - s_mood_t0;
  EyePose  pose = { SHAPE_OPEN, 0, 0, EYE_OPEN_W, EYE_OPEN_H };

  switch (s_mood) {
    case FACE_THINKING: {
      /* Eyes up, sweeping left <-> right like reading. */
      uint32_t ph = t % 2400;
      uint32_t v  = (ph < 1200) ? ph : 2400 - ph;
      s_look_x = (int8_t)(-3 + (int32_t)(v * 6 / 1200));
      pose.dx  = s_look_x;
      pose.dy  = -2;
      pose.h   = blink_height(now, 10);
      break;
    }

    case FACE_DONE:
      pose.shape = SHAPE_HAPPY;
      pose.dy    = (t < 1200 && ((t / 150) & 1)) ? -1 : 0;   /* little bounce */
      if (t >= DONE_HOLD_MS) Face_SetMood(FACE_IDLE);
      break;

    case FACE_UNDO:
      if (t < UNDO_SHOCK_MS) {                 /* O  O  wide-eyed shock */
        pose.w = 6;
        pose.h = 14;
      } else if (t < UNDO_SQUEEZE_MS) {        /* >  <  squeeze + shake */
        pose.shape = SHAPE_CHEVRON;
        pose.dx    = ((t / 60) & 1) ? 1 : -1;
      } else if (t < UNDO_DAZED_MS) {          /* -  -  dazed recovery  */
        pose.h = 4;
      } else {
        Face_SetMood(FACE_IDLE);
      }
      s_look_x = 0;
      break;

    case FACE_IDLE:
    default:
      if ((int32_t)(now - s_next_glance) >= 0) {
        static const int8_t targets[] = { 0, 0, -3, 3, -2, 2 };
        s_look_target = targets[rnd() % sizeof targets];
        s_next_glance = now + 1500 + rnd() % 3500;
      }
      if (s_look_x < s_look_target) s_look_x++;
      else if (s_look_x > s_look_target) s_look_x--;
      pose.dx = s_look_x;
      pose.h  = blink_height(now, EYE_OPEN_H);
      break;
  }

  render_eye(0, &pose);
  render_eye(1, &pose);
  s_force_redraw = 0;
}
