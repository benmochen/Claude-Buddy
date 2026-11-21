/**
 * audio.h - Plays the voice clips (audio_clips.c) through the DAC on PA4
 * (Arduino D7), into the speaker's 3.5 mm jack through a 10 uF capacitor.
 *
 * Timer 6 interrupts 8000 times per second; each interrupt writes the next
 * sample to the DAC. Playing runs entirely in that interrupt, so the main
 * loop (face animation, serial link) keeps running while the toy talks.
 */
#ifndef AUDIO_H
#define AUDIO_H

#include <stdint.h>

/* Set up PA4 as DAC output and Timer 6. Call once at startup, after the
 * clock is configured. Leaves the DAC at mid-level (silence). */
void Audio_Init(void);

/* Play the clip with this name ("yay", "beep", ...), cutting off whatever
 * was playing. Returns 1 if found, 0 if there is no clip with that name. */
int Audio_Play(const char *name);

/* Stop playing right away. */
void Audio_Stop(void);

/* 1 while a clip is playing, 0 when silent. */
int Audio_IsPlaying(void);

#endif /* AUDIO_H */
