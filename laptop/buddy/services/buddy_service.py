# The service layer: all the decisions live here.
# The API routes only receive HTTP requests and call these methods.
# Same split as a @Service class called by a @RestController in Spring Boot.

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from buddy.checkpoint import TurnCheckpoint
from buddy.messages import LCD_WIDTH, MessageStore
from buddy.state import BuddyState

logger = logging.getLogger(__name__)


# One level of nagging. frozen=True makes it read-only after creation.
@dataclass(frozen=True)
class EscalationStep:
    after_seconds: int   # seconds after the camera decided you're not looking
    state: BuddyState    # mood to switch to
    lcd_text: str        # row 2 of the LCD (max 16 chars)
    sound: str           # which group of voice lines to pick from (SOUND_GROUPS)


# Every moment the buddy talks, and the voice lines (buddy/sounds/<name>.mp3)
# it picks from at random, never the same one twice in a row. A name whose
# .mp3 doesn't exist yet is skipped, so recording it later is enough: no
# code change. For the board, also rerun firmware/tools/make_audio_clips.py.
# What each recorded clip actually says (transcribed Nov 21); names without
# a clip yet show the planned text.
SOUND_GROUPS: Dict[str, List[str]] = {
    # Claude just finished.
    "yay": [
        "yay",           # "Okay, I'm done. Come look."
        "yay_2",         # (not recorded) "Finished. Come look."
        "yay_3",         # "All done! You can look now!"
    ],
    # Claude needs permission (played right away, and again when nagging).
    "needs_you": [
        "needs_you_1",   # "I need your permission for something."
        "needs_you_2",   # "Quick question, can I do this?"
        "needs_you_3",   # "I'm stuck until you say yes!"
    ],
    # First nag after you looked away from a finished answer.
    "done": ["done"],    # "I finished. You're welcome, I guess."
    # Next nags: disappointed.
    "annoyed": [
        "annoyed",       # "You're on your phone. That's fine. I'll just wait here."
        "annoyed2",      # "I wrote 400 lines for you, you didn't even look." (big turns only)
        "annoyed_3",     # (not recorded) "I'll just wait. Again."
        "annoyed_4",     # "Is that phone more interesting than me?"
    ],
    # Last nags: fed up.
    "yelling": [
        "yelling",       # "Okay, seriously? Put the phone down. Please."
        "yelling2",      # "Hello? I'm right here! Look at the screen!"
        "yelling_3",     # (not recorded) "Phone. Down. Now."
        "yelling_4",     # "I can see you, you know."
    ],
    # After the last repeat, before going quiet.
    "gave_up": ["gave_up"],  # "Fine, I'll just wait here."
    # You looked back during the early, disappointed nags.
    "thanks": [
        "thanks",        # "Thank you."
        "thanks_2",      # "There you are."
    ],
    # You looked back after it had already yelled: no cheerful "There you are."
    "thanks_finally": ["thanks_3"],  # "Finally, thank you."
    # The redo button (no longer on the toy).
    "slam": [
        "slam",          # "Ow! Okay, I'll do it again, like always."
        "slam_2",        # "Fine. I'll try again."
        "slam_3",        # "Rude! Redoing it."
    ],
    "redo_failed": ["redo_failed"],  # (not recorded) "I can't reach Claude. Check the terminal."
    # A head slap that undid Claude's last turn.
    "undo": [
        "undo",          # "Fine. I undid it."
        "undo_2",        # (not recorded) "Undone. Like it never happened."
    ],
    "nothing_to_undo": ["nothing_to_undo"],  # "Nothing to undo. I didn't touch anything."
    # A head slap while Claude is still working.
    "busy": ["busy_1", "busy_2"],  # (not recorded) "I'm still working. Hold on."
    # A knock-knock opened a second chat.
    "new_chat": ["new_chat"],  # (not recorded) "Another one? Fine. New chat."
}

# "I wrote 400 lines for you" sounds silly after a 3-line answer. Lines listed
# here only play when Claude wrote at least BIG_TURN_LINES lines in its turn
# (counted from the files it edited, see TurnCheckpoint.lines_added()).
BIG_TURN_LINES = 100
ONLY_AFTER_BIG_TURN = ("annoyed2",)


# Tune these numbers for the demo. Shorter = funnier on stage.
# The camera already waits 2 s of not looking before saying "distracted",
# so step 0 fires right away at that point. The clips are 2 to 5 s long,
# so 8 s apart leaves a short silence between lines. A step also waits
# for the previous line to finish, so lines never cut each other off.

# After Claude finished (DONE): proud, then disappointed, then fed up.
ESCALATION_STEPS = [
    EscalationStep(0, BuddyState.ANNOYED, "HEY. LOOK UP.", "done"),
    EscalationStep(8, BuddyState.ANNOYED, "HEY. LOOK UP.", "annoyed"),
    EscalationStep(16, BuddyState.ANNOYED, "HEY. LOOK UP.", "annoyed"),   # a different annoyed line
    EscalationStep(24, BuddyState.YELLING, "LOOK AT ME!!!", "yelling"),
]

# While Claude waits on a permission prompt (NEEDS_YOU). The "I finished"
# lines would make no sense here. A needs_you line already played when the
# prompt appeared, so this one is a different one.
NEEDS_YOU_STEPS = [
    EscalationStep(0, BuddyState.ANNOYED, "HEY. LOOK UP.", "needs_you"),
    EscalationStep(8, BuddyState.YELLING, "LOOK AT ME!!!", "yelling"),
]

# After the last step, a random yelling line this often, forever: only a tap
# on the buddy (or a new prompt) stops it. Bring the work window back with a
# tap, the buddy calms down.
REPEAT_EVERY_SECONDS = 12

# Being in another app (not Terminal / VS Code) counts as "not locked in"
# once it lasts this long, so a quick Cmd+Tab to copy something is fine.
# Same 2 s the camera waits before saying "distracted".
OTHER_APP_GRACE_SECONDS = 2.0

# How often the watch loop asks the camera "distracted?" while waiting.
# The camera itself checks 15 times per second; 4 per second here is
# enough to react fast without busy-looping.
WATCH_EVERY_SECONDS = 0.25

# What the redo button types into Claude Code. One line only: a newline
# would press Enter halfway through. A bare "redo it" gives Claude nothing
# to work with, so it asks Claude to find the problems first.
REDO_AFTER_UNDO_MESSAGE = (
    "I undid all the file changes from your last answer, so the files are back "
    "to how they were before it. That wasn't good enough. Before redoing it, "
    "list what might be wrong with your last answer (bugs, wrong assumptions, "
    "things you skipped or didn't check). Then redo it with a different approach."
)
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
    def __init__(self, output, speaker, detector, claude_input, messages: MessageStore,
                 focuser, checkpoint: TurnCheckpoint) -> None:
        # output:       anything with show(state, text)   (SerialOutput or ConsoleOutput)
        # speaker:      anything with play(name), stop(), is_busy(), current_sound() (Speaker)
        # detector:     anything with is_distracted()     (AttentionDetector, or AlwaysDistracted)
        # claude_input: anything with async send(text)    (TmuxTyper)
        # messages:     the LCD text for IDLE/WORKING/DONE/NEEDS_YOU, editable from the web page
        # focuser:      anything with is_in_front(), focus() (WindowFocuser)
        # checkpoint:   copies of files from before Claude's latest turn
        self._output = output
        self._speaker = speaker
        self._detector = detector
        self._claude_input = claude_input
        self._messages = messages
        self._focuser = focuser
        self._checkpoint = checkpoint

        self._state = BuddyState.IDLE
        # The text currently on the LCD, so the web page can preview it.
        self._text = messages.get(BuddyState.IDLE)
        # Goes up by one on every state change, even DONE -> DONE, so the
        # web page can tell "a new DONE happened" from "still the same DONE".
        self._change_id = 0
        # Goes up by one on every slap and every undo-button press, so the phone
        # face can show "> <" for a moment (it watches for this number to change).
        self._reaction_id = 0
        # Who caused the last change: "hook", "nag", "button" or "manual" (the web page).
        self._source = "startup"
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
        # The line each sound group played last, so _say() doesn't repeat it.
        self._last_line: Dict[str, str] = {}
        # Lines Claude wrote in its latest turn (set when it finishes).
        self._lines_added = 0
        # True once it yelled in the current nagging stretch (for which thanks).
        self._yelled = False

    # ---- Called by the hook routes ----

    def on_prompt_submitted(self) -> None:
        # You're back: stop watching and nagging immediately, mid-sentence if needed.
        self._stop_watching()
        # Exception: the slam reaction. The redo button types a prompt, which
        # fires this hook half a second later; that must not cut off "Ow".
        if self._speaker.current_sound() not in SOUND_GROUPS["slam"]:
            self._speaker.stop()
        # A new turn starts: the previous turn's changes can no longer be undone.
        self._checkpoint.start()
        self._set_state(BuddyState.WORKING, self._messages.get(BuddyState.WORKING), "hook")

    def on_before_edit(self, file_path: str) -> None:
        # PreToolUse hook: Claude is about to change this file. Save a copy first.
        self._checkpoint.save_before_edit(file_path)

    def on_tool_finished(self) -> None:
        # PostToolUse hook: Claude just ran a tool. If it was waiting on a
        # permission prompt, you answered it and Claude carried on, so stop
        # nagging about it (otherwise only a tap would stop the yelling).
        if self._waiting_for == BuddyState.NEEDS_YOU:
            logger.info("Permission answered, Claude is working again")
            self._stop_watching()
            self._speaker.stop()
            self._set_state(BuddyState.WORKING, self._messages.get(BuddyState.WORKING), "hook")

    def on_claude_finished(self, last_assistant_message: Optional[str]) -> None:
        self._last_assistant_message = last_assistant_message
        # How much Claude wrote decides whether "I wrote 400 lines" may play.
        self._lines_added = self._checkpoint.lines_added()
        logger.info("Claude wrote %d lines this turn", self._lines_added)
        text = self._messages.get(BuddyState.DONE)
        self._set_state(BuddyState.DONE, text, "hook")
        self._say("yay")
        self._start_watching(BuddyState.DONE)

    def on_needs_input(self) -> None:
        text = self._messages.get(BuddyState.NEEDS_YOU)
        self._set_state(BuddyState.NEEDS_YOU, text, "hook")
        self._say("needs_you")   # "I need your permission for something."
        self._start_watching(BuddyState.NEEDS_YOU)

    # ---- Called by the button route and the STM32 serial reader ----

    async def on_button_pressed(self) -> str:
        # Returns a short result string for the curl reply and the log.
        self._reaction_id += 1                 # phone face shows "> <" for a moment
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
        # Cuts off any nag line first, then "Ow. Okay. I'll do it again." or similar.
        self._say("slam")
        self._set_state(BuddyState.WORKING, "redoing...", "button")

        # Type the message into Claude Code. When Claude receives it, the
        # UserPromptSubmit hook fires and sets WORKING as usual.
        sent = await self._claude_input.send(REDO_MESSAGE)
        if not sent:
            # Usually means Claude isn't running inside `tmux new -s claude`.
            self._set_state(BuddyState.DONE, "REDO FAILED", "button")
            self._say("redo_failed")
            return "failed: could not type into tmux session 'claude' (see server log)"
        return "sent"

    # ---- Called by the slap route and the STM32 serial reader ----

    async def on_slap(self) -> str:
        # Someone tapped (slapped) the buddy's head. Three cases:
        #   1. It's nagging you: you're forgiven. Bring the work window
        #      (Terminal) to the front, say thanks, stop nagging. Nothing else.
        #   2. You're in another app: bring the work window to the front.
        #   3. You're locked in (work window in front, not nagging) and Claude
        #      has finished: "I don't like this answer". Undo the files Claude
        #      changed in its last turn, then tell Claude to redo it.
        # The phone face shows "> <" for a moment.
        self._reaction_id += 1

        if self._nagging:
            return await self._forgive()

        work_in_front = await asyncio.to_thread(self._focuser.is_in_front)
        if not work_in_front:
            if await asyncio.to_thread(self._focuser.focus):
                return "focused"
            return "failed: could not bring the Claude Code app to the front (see server log)"

        if self._state == BuddyState.WORKING:
            self._say("busy")   # (not recorded yet, so silent) "I'm still working."
            return "ignored: Claude is still working"
        if self._waiting_for == BuddyState.NEEDS_YOU or self._state == BuddyState.NEEDS_YOU:
            # Typing now would land in the permission menu and pick an option.
            return "ignored: Claude is waiting on a permission prompt"
        if self._state == BuddyState.IDLE:
            self._say("nothing_to_undo")
            return "ignored: Claude hasn't answered anything yet"
        return await self._undo_and_redo()

    async def on_knock(self) -> str:
        # Knock-knock on the head: open ANOTHER Claude chat in a new tmux
        # window. The current chat is left alone (still running, still has
        # its conversation). Allowed any time, even while Claude works: that's
        # a good moment to start something else in parallel.
        self._reaction_id += 1                 # phone face shows "> <" for a moment
        # Bring Terminal forward so you see the new chat.
        await asyncio.to_thread(self._focuser.focus)
        if not await asyncio.to_thread(self._claude_input.open_new_chat):
            self._say("redo_failed")
            return "failed: could not open a tmux window in session 'claude' (see server log)"
        # Stop nagging about the old chat: you're clearly at the desk.
        if self._nagging:
            self._stop_watching()
            self._set_state(BuddyState.IDLE, self._messages.get(BuddyState.IDLE), "knock")
        self._say("new_chat")
        return "opened a new chat"

    async def _forgive(self) -> str:
        # A tap while it's nagging: the only thing that stops the yelling.
        waiting_for = self._waiting_for
        yelled = self._yelled
        await asyncio.to_thread(self._focuser.focus)    # work window to the front
        if waiting_for is None:
            waiting_for = BuddyState.DONE
        # Says thanks (cuts off the nag line) and goes back to DONE / NEEDS_YOU.
        self._thank_and_settle(waiting_for, yelled, "slap")
        # Start watching again from scratch: look away again and it starts
        # over from the first line.
        self._start_watching(waiting_for)
        return "forgiven: stopped nagging, work window in front"

    async def _undo_and_redo(self) -> str:
        # Locked-in tap after Claude finished: "that was bad, redo it".
        # Stop watching and switch to WORKING BEFORE typing: typing takes half
        # a second, and a second tap meanwhile sees WORKING and is ignored, so
        # Claude never gets the message twice.
        self._stop_watching()
        restored = 0
        if self._checkpoint.file_count() > 0:
            restored = self._checkpoint.undo()
        # "Ow! Okay, I'll do it again, like always." / "Rude! Redoing it." ...
        self._say("slam")
        self._set_state(BuddyState.WORKING, "redoing...", "slap")
        # Tell Claude its file changes were undone, so it doesn't trust its
        # memory of the files.
        if restored > 0:
            message = REDO_AFTER_UNDO_MESSAGE
        else:
            message = REDO_MESSAGE
        sent = await self._claude_input.send(message)
        if not sent:
            # Usually means Claude isn't running inside `tmux new -s claude`.
            # Shortcut: the files stay undone even though the redo failed.
            self._set_state(BuddyState.DONE, "REDO FAILED", "slap")
            self._say("redo_failed")
            return f"undid {restored} files, but could not type into tmux session 'claude'"
        return f"undid {restored} files, asked Claude to redo"

    # ---- Called by the web page ----

    def set_mood(self, state: BuddyState) -> None:
        # Only moods with an editable message can be set by hand; the nag
        # moods (ANNOYED, YELLING) come from the timer only.
        if state.value not in self._messages.all():
            raise ValueError(f"{state.value} can only be reached by the nag timer")
        # A hand-picked mood should stay put, so stop watching and nagging first.
        self._stop_watching()
        self._speaker.stop()
        self._set_state(state, self._messages.get(state), "manual")

    def get_messages(self) -> Dict[str, str]:
        return self._messages.all()

    def update_messages(self, changes: Dict[str, str]) -> Dict[str, str]:
        result = self._messages.update(changes)
        self._reshow_if_edited(changes)
        return result

    def reset_messages(self) -> Dict[str, str]:
        result = self._messages.reset()
        self._reshow_if_edited(result)
        return result

    # ---- Called by the status route ----

    def get_face_state(self) -> dict:
        # The little the phone face needs. Kept separate from get_status() so
        # devices on the network see only the mood, not the camera or messages.
        return {"state": self._state, "reaction_id": self._reaction_id}

    def get_status(self) -> dict:
        seconds_in_state = time.monotonic() - self._state_changed_at
        watching = self._watch_task is not None and not self._watch_task.done()
        return {
            "state": self._state,
            "text": self._text,
            "seconds_in_state": round(seconds_in_state, 1),
            "change_id": self._change_id,
            "source": self._source,
            "has_last_message": self._last_assistant_message is not None,
            "watching_camera": watching,
            "nagging": self._nagging,
            "distracted": self._detector.is_distracted(),
        }

    # ---- Watching the camera while Claude waits for you ----

    def _start_watching(self, waiting_state: BuddyState) -> None:
        # Only ever one watch loop: kill any old one first.
        self._stop_watching()
        self._waiting_for = waiting_state
        # create_task runs _watch() in the background on FastAPI's event
        # loop, so this method returns right away and the hook gets its 204
        # reply immediately. We keep a reference in self._watch_task:
        # asyncio only keeps weak references to tasks, so an unreferenced
        # task can be garbage-collected mid-run.
        self._watch_task = asyncio.create_task(self._watch(waiting_state))

    def _stop_watching(self) -> None:
        if self._watch_task is not None and not self._watch_task.done():
            # cancel() makes the task's current `await asyncio.sleep(...)`
            # raise CancelledError, which ends the task cleanly.
            self._watch_task.cancel()
        self._watch_task = None
        self._nagging = False
        self._yelled = False
        self._waiting_for = None

    async def _watch(self, waiting_state: BuddyState) -> None:
        # waiting_state: DONE or NEEDS_YOU, which picks the lines.
        # Two phases:
        #   - Not nagging yet: wait until you're "not locked in": the camera
        #     says you're looking away, or another app than Terminal / VS Code
        #     has been in front for 2 s.
        #   - Nagging: escalate, then yell every 12 s forever. It stops when
        #     you're locked in again (looking at the screen AND Terminal /
        #     VS Code in front), on a tap (on_slap -> _forgive), a new prompt,
        #     or when the permission prompt is answered.
        if waiting_state == BuddyState.NEEDS_YOU:
            steps = NEEDS_YOU_STEPS
        else:
            steps = ESCALATION_STEPS
        try:
            nag_started_at = 0.0   # when the current nagging stretch began
            last_nag_at = 0.0      # when we last spoke
            next_step = 0          # index of the next step in `steps`
            other_app_since = 0.0  # when another app came to the front, 0 = work app in front

            while True:
                await asyncio.sleep(WATCH_EVERY_SECONDS)
                now = time.monotonic()

                # Is the work app (Terminal / VS Code) in front? Asked in a
                # thread because it runs two small macOS commands.
                work_in_front = await asyncio.to_thread(self._focuser.is_in_front)
                looking = not self._detector.is_distracted()

                if self._nagging:
                    # Back for real: looking at the screen AND the work app in
                    # front. Let the line playing finish, then calm down.
                    if looking and work_in_front:
                        if self._speaker.is_busy():
                            continue
                        logger.info("Locked in again, calming down")
                        self._calm_down(waiting_state)
                        other_app_since = 0.0
                        continue

                if not self._nagging:
                    if work_in_front:
                        other_app_since = 0.0
                    elif other_app_since == 0.0:
                        other_app_since = now
                    in_other_app = other_app_since > 0.0 and now - other_app_since >= OTHER_APP_GRACE_SECONDS
                    if looking and not in_other_app:
                        continue                  # locked in: nothing to say
                    # Not locked in. Wait while a line is still playing (for
                    # example "yay" right after Claude finished).
                    if self._speaker.is_busy():
                        continue
                    self._nagging = True
                    self._yelled = False
                    nag_started_at = now
                    next_step = 0
                    logger.info("Not locked in, starting to nag")

                # Nagging. Never start a line while one is still playing.
                if self._speaker.is_busy():
                    continue
                if next_step < len(steps):
                    # Still working through the steps.
                    step = steps[next_step]
                    if now - nag_started_at >= step.after_seconds:
                        self._nag(step)
                        last_nag_at = now
                        next_step += 1
                        if step.state == BuddyState.YELLING:
                            self._yelled = True
                elif now - last_nag_at >= REPEAT_EVERY_SECONDS:
                    # All steps done: a random yelling line every 12 s, until a tap.
                    last_step = steps[-1]
                    self._nag(EscalationStep(0, last_step.state, last_step.lcd_text, "yelling"))
                    last_nag_at = now
                    self._yelled = True

        except asyncio.CancelledError:
            # Normal: a new event stopped the loop. Must be re-raised so
            # asyncio knows the cancel worked.
            raise
        except Exception:
            # Anything else is a real bug. Log it with the full traceback
            # instead of letting the background task die silently.
            logger.exception("Watch loop crashed")

    def _calm_down(self, waiting_state: BuddyState) -> None:
        # Called by the watch loop when you're locked in again while it nags.
        self._thank_and_settle(waiting_state, self._yelled, "nag")
        self._nagging = False
        self._yelled = False

    def _thank_and_settle(self, waiting_state: BuddyState, yelled: bool, source: str) -> None:
        # After yelling, a fed-up "Finally, thank you."; after the early nags,
        # a lighter "Thank you." / "There you are.". Then back to DONE / NEEDS_YOU.
        if yelled:
            self._say("thanks_finally")
        else:
            self._say("thanks")
        self._set_state(waiting_state, self._messages.get(waiting_state), source)

    def _nag(self, step: EscalationStep) -> None:
        self._set_state(step.state, step.lcd_text, "nag")
        self._say(step.sound)

    # ---- Internal ----

    def _say(self, group: str) -> None:
        # Play a random line from SOUND_GROUPS[group], skipping lines whose
        # .mp3 doesn't exist and the line this group played last time.
        candidates = []
        for name in SOUND_GROUPS[group]:
            if not self._speaker.has_sound(name):
                continue
            if name in ONLY_AFTER_BIG_TURN and self._lines_added < BIG_TURN_LINES:
                continue                          # e.g. no "400 lines" after a tiny answer
            candidates.append(name)
        if not candidates:
            logger.info("No voice line recorded for %r yet, staying quiet", group)
            return
        if len(candidates) > 1 and self._last_line.get(group) in candidates:
            candidates.remove(self._last_line[group])
        name = random.choice(candidates)
        self._last_line[group] = name
        self._speaker.play(name)

    def _reshow_if_edited(self, changed: Dict[str, str]) -> None:
        # If the message for the mood the buddy is in just changed, show the
        # new text right away instead of on the next mood change.
        if self._state.value in changed:
            self._set_text(self._messages.get(self._state))

    def _set_text(self, text: str) -> None:
        self._text = text
        self._output.show(self._state, text)

    def _set_state(self, new_state: BuddyState, text: str, source: str) -> None:
        if len(text) > LCD_WIDTH:
            # Fail loudly during development instead of silently cutting
            # text off on the LCD.
            raise ValueError(f"LCD text is {len(text)} chars, max is {LCD_WIDTH}: {text!r}")

        old_state = self._state
        self._state = new_state
        self._state_changed_at = time.monotonic()
        self._change_id += 1
        self._source = source
        logger.info("State %s -> %s (%s)", old_state.value, new_state.value, source)
        self._set_text(text)
