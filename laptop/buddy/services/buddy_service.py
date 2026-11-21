# The service layer: all the decisions live here.
# The API routes only receive HTTP requests and call these methods.
# Same split as a @Service class called by a @RestController in Spring Boot.

import logging
import time
from typing import Optional

from buddy.state import BuddyState

logger = logging.getLogger(__name__)

# The LCD has 16 characters per row, so every message must fit in 16.
LCD_WIDTH = 16


class BuddyService:
    def __init__(self, output) -> None:
        # output is anything with a show(state, text) method
        # (ConsoleOutput now, a serial version later).
        self._output = output
        self._state = BuddyState.IDLE

        # time.monotonic() is a clock that never jumps backwards
        # (unlike the wall clock when macOS syncs time), so it is the
        # right one for measuring "how many seconds since X".
        self._state_changed_at = time.monotonic()

        # Claude's final message from the last Stop hook. Kept in memory
        # for later (the roast generator will read it). Never printed,
        # because it can contain anything Claude wrote, including secrets.
        self._last_assistant_message: Optional[str] = None

    # ---- Called by the hook routes ----

    def on_prompt_submitted(self) -> None:
        self._set_state(BuddyState.WORKING, "thinking...")

    def on_claude_finished(self, last_assistant_message: Optional[str]) -> None:
        self._last_assistant_message = last_assistant_message
        self._set_state(BuddyState.DONE, "DONE. LOOK UP.")

    def on_needs_input(self) -> None:
        self._set_state(BuddyState.NEEDS_YOU, "NEEDS YOU!")

    # ---- Called by the status route ----

    def get_status(self) -> dict:
        seconds_in_state = time.monotonic() - self._state_changed_at
        has_message = self._last_assistant_message is not None
        return {
            "state": self._state,
            "seconds_in_state": round(seconds_in_state, 1),
            "has_last_message": has_message,
        }

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
