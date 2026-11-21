# The LCD line the buddy shows for each mood, editable from the web page.
# Saved as JSON so your edits survive a restart.

import json
import logging
import os
from pathlib import Path
from typing import Dict

from buddy.state import BuddyState

logger = logging.getLogger(__name__)

# The LCD has 16 characters per row, so every message must fit in 16.
LCD_WIDTH = 16

DEFAULT_MESSAGES: Dict[BuddyState, str] = {
    # Short symbols read at a glance from across the desk.
    BuddyState.IDLE: "zzz",
    BuddyState.WORKING: "...",
    BuddyState.DONE: "Done",
    BuddyState.NEEDS_YOU: "!!!",
}


def default_config_path() -> Path:
    # BUDDY_CONFIG overrides; otherwise the usual per-user config folder.
    override = os.environ.get("BUDDY_CONFIG")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "claude-buddy" / "messages.json"


def validate_message(text: str) -> str:
    # The character LCD only knows plain printable ASCII.
    if len(text) > LCD_WIDTH:
        raise ValueError(f"must be {LCD_WIDTH} characters or fewer (got {len(text)})")
    bad = []
    for ch in text:
        # " " to "~" is exactly the printable ASCII range.
        if not (" " <= ch <= "~") and ch not in bad:
            bad.append(ch)
    if bad:
        raise ValueError(f"the LCD can't show {''.join(bad)!r}; use plain letters, numbers and punctuation")
    return text


class MessageStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._messages = dict(DEFAULT_MESSAGES)
        self._load()

    def get(self, state: BuddyState) -> str:
        return self._messages[state]

    def all(self) -> Dict[str, str]:
        result = {}
        for state, text in self._messages.items():
            result[state.value] = text
        return result

    def update(self, changes: Dict[str, str]) -> Dict[str, str]:
        # Validate everything first so a bad field doesn't half-apply.
        parsed: Dict[BuddyState, str] = {}
        for key, text in changes.items():
            state = BuddyState(key)  # ValueError for unknown moods
            if state not in DEFAULT_MESSAGES:
                # ANNOYED and YELLING use the nag timer's fixed lines.
                raise ValueError(f"{key} has no editable message")
            parsed[state] = validate_message(text)
        self._messages.update(parsed)
        self._save()
        return self.all()

    def reset(self) -> Dict[str, str]:
        self._messages = dict(DEFAULT_MESSAGES)
        self._save()
        return self.all()

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text())
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable %s (%s); using defaults", self._path, exc)
            return
        for key, text in raw.items():
            if key not in DEFAULT_MESSAGES:
                continue
            try:
                self._messages[BuddyState(key)] = validate_message(str(text))
            except ValueError:
                logger.warning("Ignoring bad saved message for %r", key)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.all(), indent=2))
        tmp.replace(self._path)  # atomic, so a crash never leaves half a file
