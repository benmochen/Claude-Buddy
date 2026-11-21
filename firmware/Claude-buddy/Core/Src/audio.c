/**
 * audio.c - Voice clips through the DAC. See audio.h.
 *
 * Written with direct register access instead of CubeMX + HAL, so nothing
 * in the .ioc has to change and no extra HAL driver files are needed.
 * The only pin used is PA4 (Arduino D7), which CubeMX leaves unconfigured.
 */
#include "audio.h"
#include "audio_clips.h"
#include "main.h"     /* chip register names (DAC1, TIM6, RCC, GPIOA) and HAL */
#include <string.h>

/* Samples per second. Must match SAMPLE_RATE in make_audio_clips.py. */
#define AUDIO_SAMPLE_RATE 8000U

/* DAC value for silence: the middle of 0..255. The capacitor blocks this
 * constant 1.65 V, so the speaker sees 0 V at rest. */
#define AUDIO_SILENCE 128U

/* Interrupt priority for Timer 6. Lower number = more urgent. USART1 (the
 * laptop link) and the HAL tick are 0; 1 means a sample can wait a few
 * microseconds for them, which is inaudible. */
#define AUDIO_IRQ_PRIORITY 1U

/* What is playing. "volatile" because the interrupt changes them while the
 * main loop reads them; it stops the compiler keeping stale copies. */
static const uint8_t *volatile clip_data = 0;
static volatile uint32_t clip_length = 0;
static volatile uint32_t clip_pos = 0;
static volatile int playing = 0;

void Audio_Init(void)
{
  /* 1. Turn on the clocks of the parts we use. Every part of the chip is
   *    off until its clock is enabled. */
  RCC->AHB2ENR |= RCC_AHB2ENR_GPIOAEN;     /* port A (for PA4)  */
  RCC->APB1ENR1 |= RCC_APB1ENR1_DAC1EN;    /* the DAC           */
  RCC->APB1ENR1 |= RCC_APB1ENR1_TIM6EN;    /* timer 6           */
  (void)RCC->APB1ENR1;                     /* read back: wait until the clocks are on */

  /* 2. PA4 in analog mode (MODER bits 8-9 = 11), no pull-up/down, so the
   *    DAC drives the pin directly. */
  GPIOA->MODER |= (3U << (4U * 2U));
  GPIOA->PUPDR &= ~(3U << (4U * 2U));

  /* 3. DAC channel 1: mode 000 = output buffer on, connected to the pin
   *    (the buffer can drive the capacitor and the speaker's input). No
   *    trigger: a write to the data register reaches the pin right away. */
  DAC1->MCR &= ~DAC_MCR_MODE1;
  DAC1->CR &= ~DAC_CR_TEN1;
  DAC1->CR |= DAC_CR_EN1;
  DAC1->DHR8R1 = AUDIO_SILENCE;            /* 8-bit right-aligned data register */

  /* 4. Timer 6 counts at the APB1 timer clock (120 MHz here) and overflows
   *    AUDIO_SAMPLE_RATE times per second. If APB1 is divided, the timer
   *    clock is twice PCLK1 (a rule of this chip family). */
  uint32_t timer_clock = HAL_RCC_GetPCLK1Freq();
  if ((RCC->CFGR & RCC_CFGR_PPRE1) != 0U) {
    timer_clock *= 2U;
  }
  TIM6->CR1 = 0;                           /* stopped                        */
  TIM6->PSC = 0;                           /* count every clock tick         */
  TIM6->ARR = timer_clock / AUDIO_SAMPLE_RATE - 1U;  /* 120 MHz / 8000 = 15000 ticks */
  TIM6->EGR = TIM_EGR_UG;                  /* load PSC/ARR now               */
  TIM6->SR = 0;                            /* clear the flag that UG just set */
  TIM6->DIER = TIM_DIER_UIE;               /* interrupt on every overflow    */

  NVIC_SetPriority(TIM6_DAC_IRQn, AUDIO_IRQ_PRIORITY);
  NVIC_EnableIRQ(TIM6_DAC_IRQn);
}

int Audio_Play(const char *name)
{
  for (uint32_t i = 0; i < AUDIO_CLIP_COUNT; i++) {
    if (strcmp(AUDIO_CLIPS[i].name, name) == 0) {
      /* Stop the timer while changing clips, so the interrupt never sees
       * half of the old clip and half of the new one. */
      TIM6->CR1 &= ~TIM_CR1_CEN;
      clip_data = AUDIO_CLIPS[i].data;
      clip_length = AUDIO_CLIPS[i].length;
      clip_pos = 0;
      playing = 1;
      TIM6->CNT = 0;
      TIM6->CR1 |= TIM_CR1_CEN;            /* start: samples begin flowing */
      return 1;
    }
  }
  return 0;
}

void Audio_Stop(void)
{
  TIM6->CR1 &= ~TIM_CR1_CEN;
  playing = 0;
  DAC1->DHR8R1 = AUDIO_SILENCE;
}

int Audio_IsPlaying(void)
{
  return playing;
}

/* Timer 6 overflow, 8000 times per second while playing. The name must be
 * exactly this: it replaces the empty default in startup_stm32l4s5vitx.s. */
void TIM6_DAC_IRQHandler(void)
{
  if (TIM6->SR & TIM_SR_UIF) {
    TIM6->SR = ~TIM_SR_UIF;                /* clear the flag, or this fires again at once */
    if (clip_pos < clip_length) {
      DAC1->DHR8R1 = clip_data[clip_pos];  /* next sample out to the pin */
      clip_pos++;
    } else {
      /* End of the clip: back to silence and stop the timer. */
      DAC1->DHR8R1 = AUDIO_SILENCE;
      TIM6->CR1 &= ~TIM_CR1_CEN;
      playing = 0;
    }
  }
}
