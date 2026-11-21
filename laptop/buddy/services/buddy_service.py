# The service layer: all the decisions live here.
# The API routes only receive HTTP requests and call these methods.
# Same split as a @Service class called by a @RestController in Spring Boot.

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from buddy.state import BuddyState

logger = logging.getLogger(__name__)

# The LCD has 16 characters per row, so every message must fit in 16.
LCD_WIDTH = 16


# One level of nagging. frozen=True makes it read-only after creation.
@dataclass(frozen=True)
class EscalationStep:
    after_seconds: int   # seconds after Claude finished
    state: BuddyState    # mood to switch to
    lcd_text: str        # row 2 of the LCD (max 16 chars)
    spoken: str          # what the laptop says out loud


# Tune these numbers for the demo. Shorter = funnier on stage.
ESCALATION_STEPS = [
    EscalationStep(10, BuddyState.ANNOYED, "HEY. LOOK UP.",
                   "Hey. Claude is done. Look at the screen."),
    EscalationStep(25, BuddyState.YELLING, "LOOK AT ME!!!",
                   "Claude finished ages ago. Get off your phone!"),
]
# After the last step, repeat it this often, this many times, then stop
# (so it doesn't yell forever if you actually left the room).
REPEAT_EVERY_SECONDS = 20
MAX_REPEATS = 3


class BuddyService:
    def __init__(self, output, speaker, detector) -> None:
        # output:   anything with show(state, text)   (ConsoleOutput now, LCD later)
        # speaker:  anything with speak(text), stop() (Speaker)
        # detector: anything with is_distracted()     (AlwaysDistracted now, webcam later)
        self._output = output
        self._speaker = speaker
        self._detector = detector

        self._state = BuddyState.IDLE
        # time.monotonic() is a clock that never jumps backwards
        # (unlike the wall clock when macOS syncs time), so it is the
        # right one for measuring "how many seconds since X".
        self._state_changed_at = time.monotonic()

        # Claude's final message from the last Stop hook. Kept in memory
        # for later (the roast generator will read it). Never printed,
        # because it can contain anything Claude wrote, including secrets.
        self._last_assistant_message: Optional[str] = None

        # The background nagging timer, if one is running.
        self._escalation_task: Optional[asyncio.Task] = None

    # ---- Called by the hook routes ----

    def on_prompt_submitted(self) -> None:
        # You're back: stop nagging immediately, mid-sentence if needed.
        self._cancel_escalation()
        self._speaker.stop()
        self._set_state(BuddyState.WORKING, "thinking...")

    def on_claude_finished(self, last_assistant_message: Optional[str]) -> None:
        self._last_assistant_message = last_assistant_message
        self._set_state(BuddyState.DONE, "DONE. LOOK UP.")
        self._start_escalation()

    def on_needs_input(self) -> None:
        self._set_state(BuddyState.NEEDS_YOU, "NEEDS YOU!")
        self._start_escalation()

    # ---- Called by the status route ----

    def get_status(self) -> dict:
        seconds_in_state = time.monotonic() - self._state_changed_at
        nagging = self._escalation_task is not None and not self._escalation_task.done()
        return {
            "state": self._state,
            "seconds_in_state": round(seconds_in_state, 1),
            "has_last_message": self._last_assistant_message is not None,
            "nagging": nagging,
        }

    # ---- Escalation (the nagging timer) ----

    def _start_escalation(self) -> None:
        # Only ever one timer: kill any old one first.
        self._cancel_escalation()
        # create_task schedules _escalate() to run in the background on
        # FastAPI's event loop, so this method returns right away and the
        # hook gets its 204 reply without waiting 25 seconds.
        # We keep a reference in self._escalation_task: asyncio only keeps
        # weak references to tasks, so an unreferenced task can be
        # garbage-collected mid-run.
        self._escalation_task = asyncio.create_task(self._escalate())

    def _cancel_escalation(self) -> None:
        if self._escalation_task is not None and not self._escalation_task.done():
            # cancel() makes the task's current `await asyncio.sleep(...)`
            # raise CancelledError, which ends the task cleanly.
            self._escalation_task.cancel()
        self._escalation_task = None

    async def _escalate(self) -> None:
        try:
            started_at = time.monotonic()

            for step in ESCALATION_STEPS:
                # Sleep until this step's time. Measured from started_at,
                # not from the previous step, so delays don't add up.
                wake_at = started_at + step.after_seconds
                await asyncio.sleep(max(0.0, wake_at - time.monotonic()))
                self._nag(step)

            last_step = ESCALATION_STEPS[-1]
            for _ in range(MAX_REPEATS):
                await asyncio.sleep(REPEAT_EVERY_SECONDS)
                self._nag(last_step)

            logger.info("Gave up nagging after %d repeats", MAX_REPEATS)

        except asyncio.CancelledError:
            # Normal: a new event stopped the timer. Must be re-raised so
            # asyncio knows the cancel worked.
            raise
        except Exception:
            # Anything else is a real bug. Log it with the full traceback
            # instead of letting the background task die silently.
            logger.exception("Escalation timer crashed")

    def _nag(self, step: EscalationStep) -> None:
        if not self._detector.is_distracted():
            logger.info("Not distracted, skipping %s", step.state.value)
            return
        self._set_state(step.state, step.lcd_text)
        self._speaker.speak(step.spoken)

    # ---- Internal ----

    def _set_state(self, new_state: BuddyState, text: str) -> None:
        if len(text) > LCD_WIDTH:
            # Fail loudly during development instead of silently cutting
            # text off on the LCD.
            raise ValueError(f"LCD text is {len(text)} chars, max is {LCD_WIDTH}: {text!r}")

        old_state = self._state
        self._state = new_state
        self._state_changed_at = time.monotonic()
        logger.info("State %s -> %s", old_state.value, new_state.value)
        self._output.show(new_state, text)
