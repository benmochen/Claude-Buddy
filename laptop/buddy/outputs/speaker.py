# Makes the buddy talk.
#
# play(name) plays the voice line buddy/sounds/<name>.mp3, in one of two places:
#   - the phone in the toy (PhoneAudio): the face page on the phone sees the
#     order in /face/state and plays the clip. Used while a face page with
#     sound turned on is polling (the user tapped its screen once).
#   - the laptop's audio output, with macOS's built-in `afplay`. Used when no
#     phone is connected, or always with BUDDY_AUDIO=laptop.
# (The STM32 speaker on D7 is no longer used; the phone replaced it.)
# speak(text) uses macOS `say` (robot voice) on the laptop. Not used anymore.

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# The folder with the voice lines: laptop/buddy/sounds/.
# __file__ is this file (laptop/buddy/outputs/speaker.py), so going up two
# folders (.parent.parent) gives laptop/buddy/.
SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"


def _clip_lengths() -> Dict[str, float]:
    # How long each clip is, in seconds, measured once at startup with
    # macOS's `afinfo`. The phone doesn't say when a clip ends, so this is
    # how is_busy() knows the toy is still talking.
    lengths: Dict[str, float] = {}
    afinfo = shutil.which("afinfo")
    if afinfo is None:
        return lengths
    for path in sorted(SOUNDS_DIR.glob("*.mp3")):
        result = subprocess.run([afinfo, str(path)], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            # The line looks like: "estimated duration: 2.821 sec"
            if "estimated duration" in line:
                lengths[path.stem] = float(line.split(":")[1].split()[0])
    return lengths


class Speaker:
    def __init__(self, quiet: bool, phone=None) -> None:
        # quiet=True prints "[PLAY] ..." instead of making sound. Use it while
        # you're working on the code so the buddy doesn't yell at your team.
        self._quiet = quiet

        # phone: the PhoneAudio (anything with is_connected(), play(name) and
        # stop()), or None to always play on the laptop.
        self._phone = phone

        # Laptop playback: the afplay/say process running, if any.
        self._current: Optional[subprocess.Popen] = None
        # Name of the clip playing (laptop or phone), None for `say`.
        self._current_name: Optional[str] = None
        # Phone playback: when the clip on the phone will have finished
        # (time.monotonic() seconds), or 0 if nothing is playing there.
        self._phone_until = 0.0

        self._lengths = _clip_lengths()

        # shutil.which finds the full path of a command, like typing
        # `which afplay` in the terminal. None if it doesn't exist (not a Mac).
        self._afplay_path = shutil.which("afplay")
        self._say_path = shutil.which("say")
        if self._afplay_path is None and not quiet:
            logger.warning("'afplay' not found, will print instead of playing sounds")

    def has_sound(self, name: str) -> bool:
        # True if sounds/<name>.mp3 exists (lets the service skip lines that
        # haven't been recorded yet).
        return (SOUNDS_DIR / f"{name}.mp3").exists()

    def play(self, name: str) -> None:
        # Plays sounds/<name>.mp3, cutting off whatever was playing before.
        path = SOUNDS_DIR / f"{name}.mp3"
        if not path.exists():
            # Missing file: say so in the log, but don't crash the buddy.
            logger.warning("Sound file missing: %s", path)
            return

        self.stop()

        if self._quiet:
            print(f"[PLAY] {name}.mp3", flush=True)
            return

        if self._phone is not None and self._phone.is_connected():
            # The phone in the toy plays it (it picks the order up within 0.3 s).
            self._phone.play(name)
            # 3 s if the length is unknown, so is_busy() still waits a bit.
            # +0.5 s for the phone's polling delay.
            self._phone_until = time.monotonic() + self._lengths.get(name, 3.0) + 0.5
            self._current_name = name
            return

        if self._afplay_path is None:
            print(f"[PLAY] {name}.mp3", flush=True)
            return

        # Popen starts afplay in the background and returns immediately,
        # so the server keeps answering hooks while the sound plays.
        # A LIST of arguments (no shell), so the file path is never run as
        # a command, whatever characters it contains.
        self._current = subprocess.Popen([self._afplay_path, str(path)])
        self._current_name = name

    def speak(self, text: str) -> None:
        # The old robot voice on the laptop, cutting off whatever was playing.
        self.stop()
        if self._quiet or self._say_path is None:
            print(f"[SAY] {text}", flush=True)
            return
        self._current = subprocess.Popen([self._say_path, text])
        self._current_name = None

    def is_busy(self) -> bool:
        # True while a sound is still playing, on the laptop or on the phone.
        # poll() returns None while the laptop process is still running.
        laptop_busy = self._current is not None and self._current.poll() is None
        phone_busy = time.monotonic() < self._phone_until
        return laptop_busy or phone_busy

    def current_sound(self) -> Optional[str]:
        # Name of the clip playing right now, or None if silent.
        if self.is_busy():
            return self._current_name
        return None

    def stop(self) -> None:
        # Cut the sound off mid-sentence, wherever it plays.
        if self._current is not None and self._current.poll() is None:
            self._current.terminate()
        if time.monotonic() < self._phone_until and self._phone is not None:
            self._phone.stop()
        self._current = None
        self._current_name = None
        self._phone_until = 0.0
