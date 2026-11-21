# Answers "is the user distracted right now?"
#
# SHORTCUT: this version always says yes, so the buddy nags as soon as
# Claude finishes. Only used with BUDDY_NO_CAMERA=1. The real one is
# attention_detector.py, which has the same methods.


class AlwaysDistracted:
    def start(self) -> None:
        pass  # no camera to open

    def stop(self) -> None:
        pass  # no camera to close

    def recalibrate(self) -> None:
        pass  # nothing to calibrate

    def is_distracted(self) -> bool:
        return True
