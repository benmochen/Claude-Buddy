# Remembers what files looked like before Claude changed them during its
# latest turn, so a slap on the buddy can put them back.
#
# How it works:
#   - A new prompt starts a new turn: forget the old copies (start()).
#   - Just before Claude's Edit/Write/MultiEdit/NotebookEdit tool runs, the
#     PreToolUse hook tells us the file path, and we save the file's current
#     bytes (save_before_edit()). Only the FIRST copy per file per turn is
#     kept, because that is the version from before Claude touched it.
#     A file that didn't exist yet is remembered as None (Claude created it).
#   - undo() writes every saved copy back and deletes files Claude created.
#
# Copies live in memory only (never logged, never written anywhere else),
# because files can contain secrets.

import difflib
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TurnCheckpoint:
    def __init__(self, project_root: Path) -> None:
        # Only files inside this folder are saved or restored. Stops a hook
        # message from making us overwrite files anywhere else on the Mac.
        self._root = project_root.resolve()
        # file path -> its bytes before Claude's first edit this turn,
        # or None if the file did not exist yet.
        self._originals: Dict[Path, Optional[bytes]] = {}

    def start(self) -> None:
        # A new prompt was sent: the previous turn can no longer be undone.
        self._originals = {}

    def save_before_edit(self, file_path: str) -> None:
        # Called by the PreToolUse hook with the path Claude is about to edit.
        path = Path(file_path).resolve()
        if not path.is_relative_to(self._root):
            # Shortcut: edits outside the project can't be undone.
            logger.info("Not saving a file outside the project")
            return
        if path in self._originals:
            return                                # already have the pre-turn copy
        if path.is_file():
            self._originals[path] = path.read_bytes()
        else:
            self._originals[path] = None          # Claude is creating it

    def file_count(self) -> int:
        # How many files Claude changed this turn (that undo() would restore).
        return len(self._originals)

    def lines_added(self) -> int:
        # How many lines Claude wrote this turn, over all the files it edited:
        # lines in the file now that weren't in the copy from before the turn
        # (new or changed lines; deleted lines don't count). Used so the buddy
        # only brags "I wrote 400 lines for you" when it really wrote a lot.
        total = 0
        for path, original in self._originals.items():
            try:
                if not path.is_file():
                    continue                      # Claude deleted it again
                # errors="replace": a binary file gives junk lines, not a crash.
                new_lines = path.read_bytes().decode(errors="replace").splitlines()
            except OSError:
                continue
            if original is None:
                old_lines = []                    # Claude created this file
            else:
                old_lines = original.decode(errors="replace").splitlines()
            # SequenceMatcher finds the matching parts of the two versions;
            # "insert" and "replace" blocks are the lines Claude wrote.
            matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "insert" or tag == "replace":
                    total += j2 - j1
        return total

    def undo(self) -> int:
        # Puts every saved file back. Returns how many files were restored.
        restored = 0
        for path, original in self._originals.items():
            try:
                if original is None:
                    # Claude created this file: remove it (if it's still there).
                    if path.is_file():
                        path.unlink()
                else:
                    # mkdir: Claude may have deleted the folder in the meantime.
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(original)
                restored += 1
            except OSError:
                # One file failing (for example, permissions) shouldn't stop the rest.
                logger.exception("Could not restore one file")
        # Forget the copies, so a second slap doesn't undo again.
        self._originals = {}
        return restored
