# Builds the one BuddyService the whole app shares, and chooses which
# output, speaker and detector it uses. This is the only file you edit
# to swap the terminal for the LCD, or the camera for AlwaysDistracted.
# Routes ask for the service with Depends(get_buddy_service), FastAPI's
# version of Spring injecting a singleton @Service bean into a controller.

import os
from pathlib import Path

from buddy.checkpoint import TurnCheckpoint
from buddy.detectors.always_distracted import AlwaysDistracted
from buddy.messages import MessageStore, default_config_path
from buddy.outputs.console_output import ConsoleOutput
from buddy.outputs.phone_audio import PhoneAudio
from buddy.outputs.serial_output import SerialOutput
from buddy.outputs.speaker import Speaker
from buddy.outputs.tmux_typer import TmuxTyper
from buddy.outputs.window_focuser import WindowFocuser
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

# The app Claude Code runs in, as a macOS bundle ID. A slap brings it to the
# front, or undoes Claude's last turn if it's already in front.
# For Terminal: BUDDY_CLAUDE_APP_ID=com.apple.Terminal
_claude_app_id = os.environ.get("BUDDY_CLAUDE_APP_ID", "com.apple.Terminal")
# Apps that count as "locked in" when they're in front (besides the one above).
_also_work_apps = ("com.apple.Terminal", "com.microsoft.VSCode")

# The project folder (the one with .claude/settings.json). Undo only ever
# touches files inside it. parents[2]: dependencies.py -> buddy -> laptop -> project.
_project_root = Path(__file__).resolve().parents[2]

if _no_serial:
    _output = ConsoleOutput()
else:
    _output = SerialOutput(port=os.environ.get("BUDDY_SERIAL"))

# Where the voice comes out. By default the phone in the toy, while its face
# page has sound on (tapped once); otherwise the laptop (afplay).
# BUDDY_AUDIO=laptop always uses the laptop, for example if the phone's sound
# misbehaves during the demo.
_phone_audio = PhoneAudio()
_laptop_audio_only = os.environ.get("BUDDY_AUDIO") == "laptop"
if _laptop_audio_only:
    _speaker_phone = None
else:
    _speaker_phone = _phone_audio

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
    speaker=Speaker(quiet=_quiet, phone=_speaker_phone),
    detector=_detector,
    # "claude" must match the name in `tmux new -s claude`.
    claude_input=TmuxTyper(session="claude", folder=str(_project_root)),
    # The LCD text per mood, editable from the web page, saved to
    # ~/.config/claude-buddy/messages.json.
    messages=MessageStore(default_config_path()),
    # Slapping the head brings this app to the front (or undoes, see checkpoint).
    focuser=WindowFocuser(bundle_id=_claude_app_id, also_work_apps=_also_work_apps),
    # Copies of files from before Claude's latest turn, for undo.
    checkpoint=TurnCheckpoint(_project_root),
)


def get_buddy_service() -> BuddyService:
    return _buddy_service


def get_output():
    # main.py starts/stops it with the server (opens and closes the serial port).
    return _output


def get_detector():
    # main.py starts/stops it with the server; /calibrate recalibrates it.
    return _detector


def get_phone_audio() -> PhoneAudio:
    # The face routes read the sound order from it and mark the phone as seen.
    return _phone_audio
