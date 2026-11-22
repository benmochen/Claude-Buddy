# The voice comes out of the phone in the toy (the same phone that shows the face).
#
# The laptop can't push anything to the phone: the phone's face page asks
# GET /face/state about 3 times a second. So this class only remembers "the
# latest sound order", and the page reads it in that answer:
#   sound_id: goes up by one on every play() and stop(). The page reacts when
#             it sees a new number (like reaction_id for slaps).
#   sound:    the clip to play now ("yay_3"), or None for "be quiet".
# The page fetches the clip as /face/sounds/<name>.mp3 and plays it.

import time
from typing import Optional

# If the page hasn't asked for 2 s, the phone counts as gone (screen locked,
# Wi-Fi lost, page closed) and the Speaker plays on the laptop instead.
SEEN_WITHIN_SECONDS = 2.0


class PhoneAudio:
    def __init__(self) -> None:
        self._sound_id = 0                      # goes up on every play/stop
        self._sound: Optional[str] = None       # clip name to play, None = silence
        self._last_seen = 0.0                   # last poll from a page with sound on

    def mark_seen(self) -> None:
        # Called by GET /face/state?audio=1: a face page with sound turned on
        # (the user tapped the screen once) is polling right now.
        self._last_seen = time.monotonic()

    def is_connected(self) -> bool:
        # True if a phone with sound on asked within the last 2 s.
        return time.monotonic() - self._last_seen < SEEN_WITHIN_SECONDS

    def play(self, name: str) -> None:
        # Tell the phone to play sounds/<name>.mp3 (cuts off the previous clip).
        self._sound_id += 1
        self._sound = name

    def stop(self) -> None:
        # Tell the phone to stop talking.
        self._sound_id += 1
        self._sound = None

    def snapshot(self) -> dict:
        # The two fields added to the /face/state answer.
        return {"sound_id": self._sound_id, "sound": self._sound}
