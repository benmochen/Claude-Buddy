/**
 * face.h - Claude Buddy's face on the 2.8" ILI9341: orange background with
 * Claude-style black pixel eyes.
 *
 *   FACE_NORMAL  "o o"   tall black eyes, random blinks and glances
 *   FACE_HAPPY   "^ ^"   chevrons with a little bounce
 *   FACE_SAD     "/. .\" small eyes with worried, slanted brows
 *   FACE_OUCH    "> <"   squeezed shut with a shake
 */
#ifndef FACE_H
#define FACE_H

#include <stdint.h>

typedef enum {
  FACE_NORMAL = 0,
  FACE_HAPPY,
  FACE_SAD,
  FACE_OUCH,
  FACE_MOOD_COUNT
} FaceMood;

void     Face_Init(void);

/* Switch mood permanently. If a Face_React reaction is playing, the new
 * mood starts when the reaction ends. */
void     Face_SetMood(FaceMood mood);

/* Show `mood` for `duration_ms`, then return to the current permanent mood. */
void     Face_React(FaceMood mood, uint32_t duration_ms);

/* The mood currently on screen (a reaction if one is running). */
FaceMood Face_GetMood(void);

/* Call every main-loop pass; rate-limits itself to ~30 fps. */
void     Face_Update(uint32_t now_ms);

#endif /* FACE_H */
