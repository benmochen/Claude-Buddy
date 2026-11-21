# Builds the one BuddyService the whole app shares, and chooses which
# output, speaker and detector it uses. This is the only file you edit
# to swap the terminal for the LCD, or AlwaysDistracted for the webcam.
# Routes ask for the service with Depends(get_buddy_service), FastAPI's
# version of Spring injecting a singleton @Service bean into a controller.

import os

from buddy.detectors.always_distracted import AlwaysDistracted
from buddy.outputs.console_output import ConsoleOutput
from buddy.outputs.speaker import Speaker
from buddy.outputs.tmux_typer import TmuxTyper
from buddy.services.buddy_service import BuddyService

# Start the server with BUDDY_QUIET=1 in front to print instead of speak.
_quiet = os.environ.get("BUDDY_QUIET") == "1"

# Created once, when this module is first imported. There must be exactly
# one, because the buddy's state lives inside it.
_buddy_service = BuddyService(
    output=ConsoleOutput(),
    speaker=Speaker(quiet=_quiet),
    detector=AlwaysDistracted(),
    # "claude" must match the name in `tmux new -s claude`.
    claude_input=TmuxTyper(session="claude"),
)


def get_buddy_service() -> BuddyService:
    return _buddy_service
