# Builds the one BuddyService the whole app shares, and chooses which
# output, speaker and detector it uses. This is the only file you edit
# to swap the terminal for the LCD, or the camera for AlwaysDistracted.
# Routes ask for the service with Depends(get_buddy_service), FastAPI's
# version of Spring injecting a singleton @Service bean into a controller.

import os

from buddy.detectors.always_distracted import AlwaysDistracted
from buddy.outputs.console_output import ConsoleOutput
from buddy.outputs.serial_output import SerialOutput
from buddy.outputs.speaker import Speaker
from buddy.outputs.tmux_typer import TmuxTyper
from buddy.services.buddy_service import BuddyService

# Start the server with BUDDY_QUIET=1 in front to print instead of speak.
_quiet = os.environ.get("BUDDY_QUIET") == "1"

# Start with BUDDY_NO_CAMERA=1 to skip the webcam (for example while
# building in VS Code). Then the buddy nags as soon as Claude finishes.
_no_camera = os.environ.get("BUDDY_NO_CAMERA") == "1"

# Start with BUDDY_CAMERA=1 if camera_test.py needed "1" to get the right camera.
_camera_index = int(os.environ.get("BUDDY_CAMERA", "0"))

# Start with BUDDY_NO_SERIAL=1 to print to the terminal only (no STM32).
# BUDDY_SERIAL=/dev/cu.usbmodemXXXX picks the port by hand; otherwise the
# first /dev/cu.usbmodem* port is used.
_no_serial = os.environ.get("BUDDY_NO_SERIAL") == "1"

if _no_serial:
    _output = ConsoleOutput()
else:
    _output = SerialOutput(port=os.environ.get("BUDDY_SERIAL"))

if _no_camera:
    _detector = AlwaysDistracted()
else:
    # Imported here, not at the top, so BUDDY_NO_CAMERA=1 works even
    # without MediaPipe installed.
    from buddy.detectors.attention_detector import AttentionDetector
    _detector = AttentionDetector(camera_index=_camera_index)

# Created once, when this module is first imported. There must be exactly
# one, because the buddy's state lives inside it.
_buddy_service = BuddyService(
    output=_output,
    speaker=Speaker(quiet=_quiet),
    detector=_detector,
    # "claude" must match the name in `tmux new -s claude`.
    claude_input=TmuxTyper(session="claude"),
)


def get_buddy_service() -> BuddyService:
    return _buddy_service


def get_output():
    # main.py starts/stops it with the server (opens and closes the serial port).
    return _output


def get_detector():
    # main.py starts/stops it with the server; /calibrate recalibrates it.
    return _detector
