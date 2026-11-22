# Types text into the Claude Code that runs inside the tmux session,
# as if you typed it on the keyboard, then presses Enter.
# Hooks can't start a new Claude turn, so this is how the redo tap
# sends Claude a new prompt. open_new_chat() starts a second Claude Code in a
# new tmux window (knock-knock on the head).

import asyncio
import logging
import shutil
import subprocess
from typing import List

logger = logging.getLogger(__name__)

# Claude Code treats text that arrives very fast as a paste. If Enter
# arrives in the same burst it can end up inside the pasted text instead
# of submitting it, so we wait a moment between the text and Enter.
PAUSE_BEFORE_ENTER_SECONDS = 0.5


class TmuxTyper:
    def __init__(self, session: str, folder: str) -> None:
        # Name of the tmux session Claude Code runs in (`tmux new -s claude`).
        self._session = session
        # The project folder: new chats start there, so they get the hooks.
        self._folder = folder

        # Full path of the tmux program, or None if it isn't installed.
        self._tmux_path = shutil.which("tmux")
        if self._tmux_path is None:
            logger.warning("'tmux' not found, the redo button won't work (brew install tmux)")

    async def send(self, text: str) -> bool:
        # Returns True if the text and Enter were both delivered.
        if self._tmux_path is None:
            return False

        # -l means "literal": type the text exactly as written. Without it,
        # tmux would treat words like "Enter" or "C-c" inside the text as
        # key presses.
        if not self._run(["send-keys", "-t", self._session, "-l", text]):
            return False

        # asyncio.sleep, not time.sleep: the server keeps answering hooks
        # during the pause instead of freezing.
        await asyncio.sleep(PAUSE_BEFORE_ENTER_SECONDS)

        # Without -l, "Enter" means the Enter key, which submits the prompt.
        return self._run(["send-keys", "-t", self._session, "Enter"])

    def open_new_chat(self) -> bool:
        # Opens a new window in the tmux session and starts a fresh Claude Code
        # in it. The current chat keeps running in its own window (switch with
        # Ctrl+b then n). The new window comes to the front, so the redo tap
        # types into the chat you're looking at.
        if self._tmux_path is None:
            return False
        # "claude:" (with the colon) = "the session named claude, next free
        # window number". -c = start in the project folder.
        return self._run(["new-window", "-t", self._session + ":", "-c", self._folder, "claude"])

    def _run(self, tmux_args: List[str]) -> bool:
        # Build the full command as a list: [tmux path, arg1, arg2, ...].
        # A list (no shell) means the text can't be run as a shell command.
        command = [self._tmux_path]
        command.extend(tmux_args)

        try:
            # capture_output=True collects tmux's error message instead of
            # printing it. timeout stops us waiting forever if tmux hangs.
            result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        except subprocess.TimeoutExpired:
            logger.warning("tmux did not answer within 2 seconds")
            return False

        # returncode 0 means success. Anything else, for example
        # "can't find session: claude", means Claude isn't running in tmux.
        if result.returncode != 0:
            logger.warning("tmux failed: %s", result.stderr.strip())
            return False
        return True
