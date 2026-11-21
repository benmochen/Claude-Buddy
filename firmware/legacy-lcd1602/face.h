/**
 * face.h - Claude Buddy's LCD face: two animated eyes with a bar between them.
 *
 * Screen layout (16x2), E = eye cell (custom glyph), # = bar:
 *
 *   col: 0123456789012345
 *   row0   EE  ####  EE
 *   row1   EE  ####  EE
 *
 * Each eye is 2x2 cells = a 10x16 pixel bitmap. The left eye uses CGRAM slots
 * 0-3 and the right eye uses slots 4-7, so the eyes can differ (wink, > <).
 */
#ifndef FACE_H
#define FACE_H

#include <stdint.h>

typedef enum {
  FACE_IDLE = 0,   /* neutral, random blinks and glances            */
  FACE_THINKING,   /* Claude is generating: eyes look up and scan   */
  FACE_DONE,       /* output finished: happy ^ ^ (auto -> IDLE)     */
  FACE_UNDO,       /* undo button hit: shocked, then > < shake      */
  FACE_MOOD_COUNT
} FaceMood;

void     Face_Init(void);
void     Face_SetMood(FaceMood mood);
FaceMood Face_GetMood(void);

/* Call as often as possible from the main loop; it rate-limits itself. */
void     Face_Update(uint32_t now_ms);

#endif /* FACE_H */
