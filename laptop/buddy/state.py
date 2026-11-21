# The moods the buddy can be in. Every other file refers to these
# names instead of raw strings, so a typo becomes an error instead of a silent bug.

from enum import Enum


class BuddyState(str, Enum):
    # Inheriting from str means BuddyState.WORKING == "WORKING" is True,
    # and FastAPI can turn it into JSON without extra work.

    IDLE = "IDLE"            # Nothing happening yet (server just started)
    WORKING = "WORKING"      # You sent a prompt, Claude is busy
    DONE = "DONE"            # Claude finished, waiting for you to look
    NEEDS_YOU = "NEEDS_YOU"  # Claude is blocked on a permission prompt
    ANNOYED = "ANNOYED"      # First nag: you ignored DONE for a while
    YELLING = "YELLING"      # Second nag and repeats: you really ignored it
