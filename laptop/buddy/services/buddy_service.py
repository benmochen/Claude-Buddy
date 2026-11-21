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
    after_seconds: int   # seconds after the camera decided you're not looking
    state: BuddyState    # mood to switch to
    lcd_text: str        # row 2 of the LCD (max 16 chars)
    spoken: str          # what the laptop says out loud


# Tune these numbers for the demo. Shorter = funnier on stage.
# The camera already waits 2 s of not looking before saying "distracted",
# so step 0 fires right away at that point.
ESCALATION_STEPS = [
    EscalationStep(0, BuddyState.ANNOYED, "HEY. LOOK UP.",
                   "Hey. Claude is done. Look at the screen."),
    EscalationStep(8, BuddyState.YELLING, "LOOK AT ME!!!",
                   "Claude finished ages ago. Get off your phone!"),
]
# After the last step, repeat it this often, this many times, then go
# quiet (so it doesn't yell forever if you actually left the room).
REPEAT_EVERY_SECONDS = 15
MAX_REPEATS = 3

# How often the watch loop asks the camera "distracted?" while waiting.
# The camera itself checks 15 times per second; 4 per second here is
# enough to react fast without busy-looping.
WATCH_EVERY_SECONDS = 0.25

# What the redo button types into Claude Code. One line only: a newline
# would press Enter halfway through. A bare "redo it" gives Claude nothing
# to work with, so it asks Claude to find the problems first.
REDO_MESSAGE = (
    "That wasn't good enough. Before redoing it, list what might be wrong "
    "with your last answer (bugs, wrong assumptions, things you skipped or "
    "didn't check). Then redo it with a different approach."
)

# The button only does something when Claude has finished and is waiting.
# WORKING: Claude is busy, the message would pile up behind the current task.
# NEEDS_YOU: Claude is showing a permission menu, typed text could pick an option.
# IDLE: nothing has happened yet, so there's nothing to redo.
REDO_ALLOWED_STATES = (BuddyState.DONE, BuddyState.ANNOYED, BuddyState.YELLING)


class BuddyService:
    def __init__(self, output, speaker, detector, claude_input) -> None:
        # output:       anything with show(state, text)   (ConsoleOutput now, LCD later)
        # speaker:      anything with speak(text), stop() (Speaker)
        # detector:     anything with is_distracted()     (AttentionDetector, or AlwaysDistracted)
        # claude_input: anything with async send(text)    (TmuxTyper)
        self._output = output
        self._speaker = speaker
        self._detector = detector
        self._claude_input = claude_input

        self._state = BuddyState.IDLE
        # time.monotonic() is a clock that never jumps backwards
        # (unlike the wall clock when macOS syncs time), so it is the
        # right one for measuring "how many seconds since X".
        self._state_changed_at = time.monotonic()

        # Claude's final message from the last Stop hook. Kept in memory
        # for later (the roast generator will read it). Never printed,
        # because it can contain anything Claude wrote, including secrets.
        self._last_assistant_message: Optional[str] = None

        # The background loop that watches the camera while Claude waits for
        # you, if one is running.
        self._watch_task: Optional[asyncio.Task] = None
        # True while the watch loop is nagging (ANNOYED or YELLING).
        self._nagging = False
        # What the watch loop is waiting on (DONE or NEEDS_YOU), or None.
        # Needed because ANNOYED/YELLING look the same either way, but the
        # button must never type into a permission menu.
        self._waiting_for: Optional[BuddyState] = None

    # ---- Called by the hook routes ----

    def on_prompt_submitted(self) -> None:
        # You're back: stop watching and nagging immediately, mid-sentence if needed.
        self._stop_watching()
        self._speaker.stop()
        self._set_state(BuddyState.WORKING, "thinking...")

    def on_claude_finished(self, last_assistant_message: Optional[str]) -> None:
        self._last_assistant_message = last_assistant_message
        self._set_state(BuddyState.DONE, "DONE. LOOK UP.")
        self._start_watching(BuddyState.DONE, "DONE. LOOK UP.")

    def on_needs_input(self) -> None:
        self._set_state(BuddyState.NEEDS_YOU, "NEEDS YOU!")
        self._start_watching(BuddyState.NEEDS_YOU, "NEEDS YOU!")

    # ---- Called by the button route (and later the serial reader) ----

    async def on_button_pressed(self) -> str:
        # Returns a short result string for the curl reply and the log.
        if self._state not in REDO_ALLOWED_STATES:
            logger.info("Button ignored in state %s", self._state.value)
            return f"ignored: state is {self._state.value}"
        if self._waiting_for == BuddyState.NEEDS_YOU:
            # ANNOYED/YELLING, but about a permission menu, not a finished answer.
            logger.info("Button ignored: Claude is showing a permission menu")
            return "ignored: Claude is waiting on a permission prompt"

        # Stop nagging and switch to WORKING BEFORE typing. Typing takes
        # half a second, and a second press during that time now sees
        # WORKING and is ignored, so Claude never gets the message twice.
        self._stop_watching()
        self._speaker.stop()
        self._set_state(BuddyState.WORKING, "redoing...")

        # Type the message into Claude Code. When Claude receives it, the
        # UserPromptSubmit hook fires and sets WORKING "thinking..." as usual.
        sent = await self._claude_input.send(REDO_MESSAGE)
        if not sent:
            # Usually means Claude isn't running inside `tmux new -s claude`.
            self._set_state(BuddyState.DONE, "REDO FAILED")
            return "failed: could not type into tmux session 'claude' (see server log)"
        return "sent"

    # ---- Called by the status route ----

    def get_status(self) -> dict:
        seconds_in_state = time.monotonic() - self._state_changed_at
        watching = self._watch_task is not None and not self._watch_task.done()
        return {
            "state": self._state,
            "seconds_in_state": round(seconds_in_state, 1),
            "has_last_message": self._last_assistant_message is not None,
            "watching_camera": watching,
            "nagging": self._nagging,
            "distracted": self._detector.is_distracted(),
        }

    # ---- Watching the camera while Claude waits for you ----

    def _start_watching(self, waiting_state: BuddyState, waiting_text: str) -> None:
        # Only ever one watch loop: kill any old one first.
        self._stop_watching()
        self._waiting_for = waiting_state
        # create_task runs _watch() in the background on FastAPI's event
        # loop, so this method returns right away and the hook gets its 204
        # reply immediately. We keep a reference in self._watch_task:
        # asyncio only keeps weak references to tasks, so an unreferenced
        # task can be garbage-collected mid-run.
        self._watch_task = asyncio.create_task(self._watch(waiting_state, waiting_text))

    def _stop_watching(self) -> None:
        if self._watch_task is not None and not self._watch_task.done():
            # cancel() makes the task's current `await asyncio.sleep(...)`
            # raise CancelledError, which ends the task cleanly.
            self._watch_task.cancel()
        self._watch_task = None
        self._nagging = False
        self._waiting_for = None

    async def _watch(self, waiting_state: BuddyState, waiting_text: str) -> None:
        # waiting_state / waiting_text: what to go back to when you look at
        # the screen again (DONE "DONE. LOOK UP." or NEEDS_YOU "NEEDS YOU!").
        try:
            nag_started_at = 0.0   # when the current nagging stretch began
            last_nag_at = 0.0      # when we last spoke
            next_step = 0          # index of the next ESCALATION_STEPS entry
            repeats_done = 0       # repeats of the last step so far

            while True:
                await asyncio.sleep(WATCH_EVERY_SECONDS)
                now = time.monotonic()

                if not self._detector.is_distracted():
                    # Looking at the screen. If we were nagging, calm down.
                    if self._nagging:
                        logger.info("Looking at the screen again, calming down")
                        self._speaker.stop()
                        self._set_state(waiting_state, waiting_text)
                        self._nagging = False
                    continue

                # Not looking. If this is the start of a new stretch, reset
                # the escalation so it begins again from step 0.
                if not self._nagging:
                    self._nagging = True
                    nag_started_at = now
                    next_step = 0
                    repeats_done = 0

                if next_step < len(ESCALATION_STEPS):
                    # Still working through the steps (ANNOYED, then YELLING).
                    step = ESCALATION_STEPS[next_step]
                    if now - nag_started_at >= step.after_seconds:
                        self._nag(step)
                        last_nag_at = now
                        next_step += 1
                elif repeats_done < MAX_REPEATS:
                    # All steps done: repeat the last one every REPEAT_EVERY_SECONDS.
                    if now - last_nag_at >= REPEAT_EVERY_SECONDS:
                        self._nag(ESCALATION_STEPS[-1])
                        last_nag_at = now
                        repeats_done += 1
                        if repeats_done == MAX_REPEATS:
                            logger.info("Gave up nagging after %d repeats", MAX_REPEATS)
                # else: gave up. Stay quiet until you look back (which calms
                # down and resets) or send a prompt (which stops this loop).

        except asyncio.CancelledError:
            # Normal: a new event stopped the loop. Must be re-raised so
            # asyncio knows the cancel worked.
            raise
        except Exception:
            # Anything else is a real bug. Log it with the full traceback
            # instead of letting the background task die silently.
            logger.exception("Watch loop crashed")

    def _nag(self, step: EscalationStep) -> None:
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
