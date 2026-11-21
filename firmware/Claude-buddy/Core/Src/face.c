/**
 * face.c - Procedural Claude-style eyes for the ILI9341.
 *
 * Each eye lives in a fixed box. Every frame the eye is drawn into an
 * off-screen buffer (orange background + black shapes) and blitted in one SPI
 * transfer, so there is no flicker. A box is only re-sent when its pose changed.
 */
#include "face.h"
#include "ili9341.h"
#include "main.h"
#include <string.h>

/* ---------------- look (edit to taste) ---------------- */
#define FACE_BG     COLOR_CLAUDE_ORANGE
#define EYE_COLOR   COLOR_BLACK

#define EYE_W       28          /* normal eye width                     */
#define EYE_H       64          /* normal eye height                    */
#define EDGE_MARGIN 0           /* px between eye box and screen edge   */
#define STROKE      10          /* line thickness for ^ ^, > <, brows   */

#define BOX_W       96          /* per-eye drawing box                  */
#define BOX_H       128
#define BOX_Y       ((TFT_H - BOX_H) / 2)
/* Eyes pushed as far apart as the screen allows. */
#define LEFT_CX     (EDGE_MARGIN + BOX_W / 2)
#define RIGHT_CX    (TFT_W - EDGE_MARGIN - BOX_W / 2)

/* ---------------- timing ---------------- */
#define FRAME_MS        33
#define HAPPY_BOUNCE_MS 1200
#define OUCH_SHAKE_MS   900

typedef enum { SHAPE_RECT, SHAPE_HAPPY, SHAPE_OUCH, SHAPE_SAD } Shape;

typedef struct {
  Shape   shape;
  int8_t  dx, dy;    /* offset from the box centre */
  uint8_t h;         /* eye height for SHAPE_RECT / SHAPE_SAD (blinks) */
} EyePose;

/* ---------------- state ---------------- */
static FaceMood s_base_mood;        /* permanent mood                */
static FaceMood s_mood;             /* what is on screen             */
static uint32_t s_mood_t0;
static uint32_t s_react_until;      /* 0 = no temporary reaction     */
static uint32_t s_last_frame;

static uint8_t  s_blinking;
static uint32_t s_blink_t0, s_next_blink;
static int8_t   s_look_x, s_look_target;
static uint32_t s_next_glance;

static EyePose  s_last_pose[2];
static uint8_t  s_force;

static uint16_t s_buf[BOX_W * BOX_H];   /* 24 KB, pre-swapped RGB565 */

static uint32_t s_rng = 0x9E3779B9u;
static uint32_t rnd(void)
{
  s_rng ^= s_rng << 13; s_rng ^= s_rng >> 17; s_rng ^= s_rng << 5;
  return s_rng;
}

/* ---------------- drawing into the box buffer ---------------- */

static void buf_fill(uint16_t color)
{
  uint16_t c = TFT_SWAP(color);
  for (uint32_t i = 0; i < BOX_W * BOX_H; i++) s_buf[i] = c;
}

static void buf_rect(int x, int y, int w, int h, uint16_t color)
{
  uint16_t c = TFT_SWAP(color);
  if (x < 0) { w += x; x = 0; }
  if (y < 0) { h += y; y = 0; }
  if (x + w > BOX_W) w = BOX_W - x;
  if (y + h > BOX_H) h = BOX_H - y;
  for (int j = 0; j < h; j++)
    for (int i = 0; i < w; i++)
      s_buf[(y + j) * BOX_W + x + i] = c;
}

/* Thick line made of square "pixels" for a chunky pixel-art look. */
static void buf_line(int x0, int y0, int x1, int y1, uint16_t color)
{
  int dx = x1 > x0 ? x1 - x0 : x0 - x1, sx = x0 < x1 ? 1 : -1;
  int dy = y1 > y0 ? y0 - y1 : y1 - y0, sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  for (;;) {
    buf_rect(x0 - STROKE / 2, y0 - STROKE / 2, STROKE, STROKE, color);
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

/* side: 0 = left eye, 1 = right eye (mirrors asymmetric shapes). */
static void render_eye(uint8_t side, const EyePose *p)
{
  int cx = BOX_W / 2 + p->dx;
  int cy = BOX_H / 2 + p->dy;
  int m  = side ? -1 : 1;           /* +1: inner side is to the right */

  buf_fill(FACE_BG);

  switch (p->shape) {
    case SHAPE_RECT:                                  /* o o */
      buf_rect(cx - EYE_W / 2, cy - p->h / 2, EYE_W, p->h, EYE_COLOR);
      break;

    case SHAPE_HAPPY:                                 /* ^ ^ */
      buf_line(cx - 22, cy + 10, cx, cy - 14, EYE_COLOR);
      buf_line(cx, cy - 14, cx + 22, cy + 10, EYE_COLOR);
      break;

    case SHAPE_OUCH:                                  /* > < */
      buf_line(cx - 14 * m, cy - 24, cx + 14 * m, cy, EYE_COLOR);
      buf_line(cx + 14 * m, cy, cx - 14 * m, cy + 24, EYE_COLOR);
      break;

    case SHAPE_SAD: {                                 /* /. .\ */
      int ey = cy + 14;                               /* eyes sit lower */
      buf_rect(cx - EYE_W / 2, ey - p->h / 2, EYE_W, p->h, EYE_COLOR);
      /* brow: low on the outer side, raised on the inner side */
      buf_line(cx - 20 * m, cy - 26, cx + 18 * m, cy - 42, EYE_COLOR);
      break;
    }
  }
}

static void draw_eye(uint8_t side, const EyePose *p)
{
  if (!s_force && memcmp(p, &s_last_pose[side], sizeof *p) == 0) return;
  s_last_pose[side] = *p;
  render_eye(side, p);
  int cx = side ? RIGHT_CX : LEFT_CX;
  TFT_DrawImage(cx - BOX_W / 2, BOX_Y, BOX_W, BOX_H, s_buf);
}

/* ---------------- behaviour ---------------- */

static uint8_t blink_height(uint32_t now, uint8_t full_h)
{
  if (!s_blinking && (int32_t)(now - s_next_blink) >= 0) {
    s_blinking = 1;
    s_blink_t0 = now;
    s_next_blink = now + 2000 + rnd() % 3500;
  }
  if (!s_blinking) return full_h;

  uint32_t t = now - s_blink_t0;
  if (t < 40)  return full_h / 2;
  if (t < 100) return 8;
  if (t < 140) return full_h / 2;
  s_blinking = 0;
  return full_h;
}

static void enter_mood(FaceMood mood, uint32_t now)
{
  s_mood        = mood;
  s_mood_t0     = now;
  s_blinking    = 0;
  s_next_blink  = now + 1000 + rnd() % 2000;
  s_look_target = 0;
  s_next_glance = now + 1500;
}

void Face_SetMood(FaceMood mood)
{
  s_base_mood   = mood;
  s_react_until = 0;
  enter_mood(mood, HAL_GetTick());
}

void Face_React(FaceMood mood, uint32_t duration_ms)
{
  uint32_t now  = HAL_GetTick();
  s_react_until = now + duration_ms;
  if (s_react_until == 0) s_react_until = 1;
  enter_mood(mood, now);
}

FaceMood Face_GetMood(void) { return s_mood; }

void Face_Init(void)
{
  s_rng ^= HAL_GetTick() * 2654435761u;
  if (!s_rng) s_rng = 1;
  TFT_FillScreen(FACE_BG);
  s_force = 1;
  Face_SetMood(FACE_NORMAL);
  s_last_frame = HAL_GetTick() - FRAME_MS;
  Face_Update(HAL_GetTick());
}

void Face_Update(uint32_t now)
{
  if (now - s_last_frame < FRAME_MS) return;
  s_last_frame = now;

  if (s_react_until && (int32_t)(now - s_react_until) >= 0) {
    s_react_until = 0;
    enter_mood(s_base_mood, now);
  }

  uint32_t t = now - s_mood_t0;
  EyePose  pose = { SHAPE_RECT, 0, 0, EYE_H };

  switch (s_mood) {
    case FACE_HAPPY:
      pose.shape = SHAPE_HAPPY;
      pose.dy    = (t < HAPPY_BOUNCE_MS && ((t / 150) & 1)) ? -6 : 0;
      break;

    case FACE_SAD:
      pose.shape = SHAPE_SAD;
      pose.dy    = (t < 400) ? (int8_t)(t / 100) : 4;     /* slow droop */
      pose.h     = blink_height(now, 40);
      break;

    case FACE_OUCH:
      pose.shape = SHAPE_OUCH;
      pose.dx    = (t < OUCH_SHAKE_MS) ? (((t / 50) & 1) ? 4 : -4) : 0;
      break;

    case FACE_NORMAL:
    default:
      if ((int32_t)(now - s_next_glance) >= 0) {
        static const int8_t targets[] = { 0, 0, 0, -10, 10 };
        s_look_target = targets[rnd() % sizeof targets];
        s_next_glance = now + 1500 + rnd() % 3500;
      }
      if (s_look_x < s_look_target) s_look_x += 2;
      else if (s_look_x > s_look_target) s_look_x -= 2;
      pose.dx = s_look_x;
      pose.h  = blink_height(now, EYE_H);
      break;
  }

  draw_eye(0, &pose);
  draw_eye(1, &pose);
  s_force = 0;
}
