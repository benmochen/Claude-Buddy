# Answers "is the user distracted right now?"
#
# SHORTCUT: this version always says yes, so the buddy nags whenever you
# don't send a new prompt in time, even if you were reading Claude's output.
# The webcam version (webcam_detector.py, later) will have the same
# is_distracted() method and replace this one in dependencies.py.


class AlwaysDistracted:
    def is_distracted(self) -> bool:
        return True
