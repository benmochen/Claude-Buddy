# Makes the buddy talk through the laptop's audio output.
# Audio goes to whatever output macOS is using, so plug the hamburger
# speaker into the headphone jack and it comes out of the speaker.
#
# Two ways to talk:
#   play(name): plays buddy/sounds/<name>.mp3 (the ElevenLabs voice lines)
#               with macOS's built-in `afplay` command.
#   speak(text): macOS `say`, the robot voice. Kept as a fallback.

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# The folder with the voice lines: laptop/buddy/sounds/.
# __file__ is this file (laptop/buddy/outputs/speaker.py), so going up two
# folders (.parent.parent) gives laptop/buddy/.
SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"


class Speaker:
    def __init__(self, quiet: bool) -> None:
        # quiet=True prints "[PLAY] ..." instead of making sound. Use it while
        # you're working on the code so the buddy doesn't yell at your team.
        self._quiet = quiet

        # The sound process currently running (afplay or say), if any,
        # and the name of the sound file it's playing (None for `say`).
        self._current: Optional[subprocess.Popen] = None
        self._current_name: Optional[str] = None

        # shutil.which finds the full path of a command, like typing
        # `which afplay` in the terminal. None if it doesn't exist (not a Mac).
        self._afplay_path = shutil.which("afplay")
        self._say_path = shutil.which("say")
        if self._afplay_path is None and not quiet:
            logger.warning("'afplay' not found, will print instead of playing sounds")

    def play(self, name: str) -> None:
        # Plays sounds/<name>.mp3, cutting off whatever was playing before.
        path = SOUNDS_DIR / f"{name}.mp3"
        if not path.exists():
            # Missing file: say so in the log, but don't crash the buddy.
            logger.warning("Sound file missing: %s", path)
            return

        self.stop()

        if self._quiet or self._afplay_path is None:
            print(f"[PLAY] {name}.mp3", flush=True)
            return

        # Popen starts afplay in the background and returns immediately,
        # so the server keeps answering hooks while the sound plays.
        # A LIST of arguments (no shell), so the file path is never run as
        # a command, whatever characters it contains.
        self._current = subprocess.Popen([self._afplay_path, str(path)])
        self._current_name = name

    def speak(self, text: str) -> None:
        # The old robot voice, cutting off whatever was playing before.
        self.stop()
        if self._quiet or self._say_path is None:
            print(f"[SAY] {text}", flush=True)
            return
        self._current = subprocess.Popen([self._say_path, text])
        self._current_name = None

    def is_busy(self) -> bool:
        # True while a sound is still playing.
        # poll() returns None while the process is still running.
        return self._current is not None and self._current.poll() is None

    def current_sound(self) -> Optional[str]:
        # Name of the sound file playing right now, or None if silent.
        if self.is_busy():
            return self._current_name
        return None

    def stop(self) -> None:
        # Cut the sound off mid-sentence.
        if self.is_busy():
            self._current.terminate()
        self._current = None
        self._current_name = None
