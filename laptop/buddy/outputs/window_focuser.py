# Brings the app that runs Claude Code (VS Code by default) to the front
# of the screen. Used when you slap the buddy's head.
#
# It uses the macOS `open -a <App>` command. If that app is already in
# front, nothing changes; if you were on Safari, Discord, etc., that
# app jumps back in front. No extra macOS permissions are needed.

import logging
import subprocess

logger = logging.getLogger(__name__)


class WindowFocuser:
    def __init__(self, app_name: str) -> None:
        # The macOS app name as shown in /Applications without ".app",
        # for example "Terminal", "iTerm", or "Visual Studio Code".
        self._app_name = app_name

    def focus(self) -> bool:
        # Returns True if macOS brought the app to the front.
        # A list (no shell), so the app name can't be run as a shell command.
        command = ["open", "-a", self._app_name]
        try:
            # timeout: don't wait forever if macOS is slow to answer.
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            logger.warning("'open -a %s' did not finish within 3 seconds", self._app_name)
            return False

        # returncode 0 means success. Anything else usually means the app
        # name is wrong ("Unable to find application named ...").
        if result.returncode != 0:
            logger.warning("Could not bring %s to the front: %s",
                           self._app_name, result.stderr.strip())
            return False
        return True
