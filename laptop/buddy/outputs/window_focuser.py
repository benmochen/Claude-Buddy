# Knows which app is in front of the screen, and can bring the app that
# runs Claude Code (VS Code by default) to the front. Used when you slap
# the buddy's head.
#
# Apps are identified by their "bundle ID", macOS's unique name for an app,
# for example "com.microsoft.VSCode" or "com.apple.Terminal". (The display
# name is less reliable: VS Code calls itself "Code" internally.)
#
# Both commands used here (`lsappinfo` and `open`) come with macOS and need
# no extra permissions.

import logging
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


class WindowFocuser:
    def __init__(self, bundle_id: str, also_work_apps=()) -> None:
        # The app Claude Code runs in, for example "com.apple.Terminal".
        # focus() brings this one to the front.
        self._bundle_id = bundle_id
        # Other apps that also count as "working" when they're in front
        # (for example VS Code), but are never brought forward.
        self._work_apps = [bundle_id]
        for app in also_work_apps:
            self._work_apps.append(app)

    def is_in_front(self) -> bool:
        # True if the app you are using right now is a work app
        # (the Claude Code app or one of also_work_apps).
        return self._front_bundle_id() in self._work_apps

    def focus(self) -> bool:
        # Brings the Claude Code app to the front. Returns True on success.
        # `open -b <bundle id>` opens the app, or just brings it forward if
        # it's already running.
        result = self._run(["open", "-b", self._bundle_id])
        return result is not None

    def _front_bundle_id(self) -> Optional[str]:
        # `lsappinfo front` prints an ID for the front app, like "ASN:0x0-0x73073:".
        front = self._run(["lsappinfo", "front"])
        if not front:
            return None
        # `lsappinfo info <ID>` prints several lines; one of them looks like
        #     bundleID="com.microsoft.VSCode"
        info = self._run(["lsappinfo", "info", front.strip()])
        if info is None:
            return None
        for line in info.splitlines():
            line = line.strip()
            if line.startswith('bundleID="'):
                # Cut off 'bundleID="' at the start and '"' at the end.
                return line[len('bundleID="'):-1]
        return None

    def _run(self, command: List[str]) -> Optional[str]:
        # Runs a command (a list, no shell). Returns its printed output,
        # or None if it failed.
        try:
            # timeout: don't wait forever if macOS is slow to answer.
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            logger.warning("%s did not finish within 3 seconds", command[0])
            return None
        # returncode 0 means success. For `open -b`, anything else usually
        # means the bundle ID is wrong ("Unable to find application ...").
        if result.returncode != 0:
            logger.warning("%s failed: %s", command[0], result.stderr.strip())
            return None
        return result.stdout
