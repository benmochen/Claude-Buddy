# Answers "is the user distracted right now?" by checking whether they are
# looking at the screen, using the webcam and Google's MediaPipe Face
# Landmarker. The landmarker finds 478 points on your face in each frame,
# and also gives:
#   - a rotation matrix: which way your head is pointing (we turn it into
#     two angles, pitch = tilt up/down, yaw = turn left/right)
#   - "blendshape" scores from 0 to 1 for facial movements, including
#     eyeLookDownLeft and eyeLookDownRight (how much your eyes look down)
#
# "Not looking" means any of: head tilted or turned away from your normal
# working position, eyes looking down, or no face in the image.
# Your normal working position is measured during the first few seconds
# (calibration), because the camera sits above the screen and everyone
# sits differently.
#
# A background thread does all of this ~15 times per second.
# is_distracted() just reads the latest result, so it's instant.

import logging
import math
import os
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

logger = logging.getLogger(__name__)

# ---- Tuning (from Ben's first test, Nov 20) ----

# How far (in degrees) your head can tilt DOWN from your working position
# before it counts as "not looking". Ben's test: reading the screen was
# 4 to 14, phone in hand 19 to 24, working position about 7.5.
# Tilting UP never counts (looking at the top of the screen is fine).
HEAD_DOWN_LIMIT_DEGREES = 10.0
# How far your head can turn left/right. Bigger, because looking at the
# edge of a wide screen turns your head more than reading does.
YAW_LIMIT_DEGREES = 30.0
# How much MORE than in your working position your eyes can look down, or
# your eyelids can drop, before it counts as "not looking" (scores 0 to 1).
# Ben's test: looking down at the phone often gave eyeLookDown near 0,
# because MediaPipe sees the lowered eyelids as "closing" (eyeBlink).
EYES_EXTRA_LIMIT = 0.35
# Several signs at once. Each sign is turned into "how much of its limit"
# (7.5 of 10 degrees down = 0.75) and the four are added up. Over this =
# not looking, even if no single sign reached its limit.
# Ben's test (Nov 22): looking at the screen added up to ~0.1; looking down
# at the phone gave down 7.6/10, turn 19.5/30, eyes 0.23/0.35, lids 0.30/0.35
# = ~2.9, with every single sign UNDER its limit.
COMBINED_LIMIT = 1.5

# How long to measure your working position at startup. Look at the screen
# normally during this time.
CALIBRATION_SECONDS = 3.0

# You must be "not looking" this long before it counts, so a glance at the
# keyboard doesn't.
SECONDS_BEFORE_DISTRACTED = 2.0
# One or two frames that say "looking" in the middle of looking away
# (noise) don't restart the 2 second count if shorter than this.
GAP_ALLOWED_SECONDS = 0.5

# How many frames per second to analyse.
CHECKS_PER_SECOND = 15

# The face model file, downloaded automatically the first time (about 4 MB).
MODEL_PATH = os.path.join("models", "face_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


# One frame's measurements. frozen=True makes it read-only after creation,
# so the server can read it while the thread is already making the next one.
@dataclass(frozen=True)
class Reading:
    face_found: bool
    pitch: float            # head tilt up/down, degrees
    yaw: float              # head turn left/right, degrees
    eyes_down: float        # 0 = eyes straight, 1 = eyes fully down
    eyelids: float          # 0 = eyes wide open, 1 = eyelids fully closed
    looking: bool           # final decision for this frame
    reason: str             # why not looking ("head down", "no face", ...) or "ok"


def _angle_difference(a: float, b: float) -> float:
    # Difference between two angles in degrees, always between -180 and 180.
    # Without this, 179 and -179 would look 358 degrees apart instead of 2.
    return (a - b + 180.0) % 360.0 - 180.0


def _head_angles(matrix) -> tuple:
    # Turn MediaPipe's 4x4 transformation matrix into (pitch, yaw) degrees.
    # The top-left 3x3 part is a rotation matrix R. These two formulas are
    # the standard way to read the x-axis (pitch) and y-axis (yaw)
    # rotation out of R.
    r21 = matrix[2][1]
    r22 = matrix[2][2]
    r20 = matrix[2][0]
    pitch = math.degrees(math.atan2(r21, r22))
    # clamp to [-1, 1] so tiny rounding errors can't crash asin
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, -r20))))
    return pitch, yaw


def _combined_score(head_down: float, yaw_off: float, eyes_extra: float, lids_extra: float) -> float:
    # Adds up how much of its own limit each sign reached. Only "away"
    # directions count: head up or eyes opening wider than usual add nothing.
    total = max(0.0, head_down) / HEAD_DOWN_LIMIT_DEGREES
    total += yaw_off / YAW_LIMIT_DEGREES
    total += max(0.0, eyes_extra) / EYES_EXTRA_LIMIT
    total += max(0.0, lids_extra) / EYES_EXTRA_LIMIT
    return total


def _average_score(blendshapes, left_name: str, right_name: str) -> float:
    # blendshapes is a list of (name, score) entries for one face.
    # Average the left and right eye scores with the given names.
    total = 0.0
    count = 0
    for shape in blendshapes:
        if shape.category_name in (left_name, right_name):
            total += shape.score
            count += 1
    if count == 0:
        return 0.0
    return total / count


class AttentionDetector:
    def __init__(self, camera_index: int = 0, keep_preview: bool = False) -> None:
        # camera_index 0 is normally the built-in FaceTime camera.
        self._camera_index = camera_index
        # keep_preview=True saves each frame with face points drawn on it,
        # for camera_test.py to display. The server doesn't need it.
        self._keep_preview = keep_preview

        self._download_model_if_missing()
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            # VIDEO mode remembers the face between frames, which is
            # faster and steadier than finding it from scratch each time.
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,                                  # only you
            output_face_blendshapes=True,                 # we need eye scores
            output_facial_transformation_matrixes=True,   # we need head angles
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        self._camera: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Calibration: samples collected during the first seconds with a face.
        self._calibration_started_at: Optional[float] = None
        self._pitch_samples: List[float] = []
        self._yaw_samples: List[float] = []
        self._eyes_samples: List[float] = []
        self._lids_samples: List[float] = []
        # Your working position, filled in when calibration finishes.
        self._base_pitch: Optional[float] = None
        self._base_yaw: Optional[float] = None
        self._base_eyes: Optional[float] = None
        self._base_lids: Optional[float] = None

        # A lock stops the thread and the server touching these at the same moment.
        self._lock = threading.Lock()
        self._latest: Optional[Reading] = None
        self._away_since: Optional[float] = None     # start of current "not looking" stretch
        self._last_away_at: Optional[float] = None   # last frame that was "not looking"
        self._preview = None

    # ---- Start / stop ----

    def start(self) -> None:
        # Open the camera HERE, not in the background thread: on macOS the
        # "allow camera access?" popup only works from the main thread.
        self._camera = cv2.VideoCapture(self._camera_index)
        if not self._camera.isOpened():
            raise RuntimeError(
                f"Could not open camera {self._camera_index}. Check System Settings > "
                "Privacy & Security > Camera, and allow your terminal app."
            )
        self._running = True
        # daemon=True: the thread doesn't stop Python from exiting.
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Attention detector started on camera %d", self._camera_index)

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._camera is not None:
            self._camera.release()
        self._landmarker.close()

    # ---- Read by the service (and camera_test.py) ----

    def is_calibrated(self) -> bool:
        return self._base_pitch is not None

    def calibration_text(self) -> str:
        # One line describing your working position, for display.
        if not self.is_calibrated():
            return "calibrating: look at the screen normally"
        return (
            f"working position: pitch {self._base_pitch:.1f}, yaw {self._base_yaw:.1f}, "
            f"eyes down {self._base_eyes:.2f}, eyelids {self._base_lids:.2f}"
        )

    def recalibrate(self) -> None:
        # Forget the working position and measure it again from the next frame.
        # Setting _base_pitch to None last makes the thread start collecting.
        self._calibration_started_at = None
        self._pitch_samples = []
        self._yaw_samples = []
        self._eyes_samples = []
        self._lids_samples = []
        self._base_pitch = None

    def latest_reading(self) -> Optional[Reading]:
        with self._lock:
            return self._latest

    def latest_preview(self):
        with self._lock:
            return self._preview

    def is_distracted(self) -> bool:
        # True if you've been "not looking" for at least 2 seconds straight.
        with self._lock:
            if self._away_since is None or self._last_away_at is None:
                return False
            now = time.monotonic()
            still_away = now - self._last_away_at <= GAP_ALLOWED_SECONDS
            long_enough = now - self._away_since >= SECONDS_BEFORE_DISTRACTED
            return still_away and long_enough

    def is_looking_now(self) -> bool:
        # Fast answer, no 2 s wait: False if ANY frame in the last 0.5 s was
        # "not looking". Used to pick WHICH nag line (phone or other app):
        # is_distracted() only turns True after 2 s, so right after you look
        # down at your phone it still says "looking" and the buddy would say
        # "another tab". Whether to nag at all still uses is_distracted().
        with self._lock:
            if self._last_away_at is None:
                return True                       # never looked away yet
            return time.monotonic() - self._last_away_at > GAP_ALLOWED_SECONDS

    def latest_reason(self) -> str:
        # Why the latest frame counts as not looking ("head down", "no face",
        # ...) or "ok". For the log next to each nag line.
        with self._lock:
            if self._latest is None:
                return "no frame yet"
            return self._latest.reason

    def latest_numbers(self) -> str:
        # The latest frame's measurements next to their limits, compared with
        # the calibrated working position. For BUDDY_SHOW_CAMERA=1, e.g.
        # "down +4.1/10 turn 2.0/30 eyes +0.03/0.35 lids +0.12/0.35"
        with self._lock:
            reading = self._latest
        if reading is None or not reading.face_found or not self.is_calibrated():
            return ""
        down = _angle_difference(reading.pitch, self._base_pitch)
        turn = abs(_angle_difference(reading.yaw, self._base_yaw))
        eyes = reading.eyes_down - self._base_eyes
        lids = reading.eyelids - self._base_lids
        total = _combined_score(down, turn, eyes, lids)
        return (f"down {down:+5.1f}/{HEAD_DOWN_LIMIT_DEGREES:.0f}  "
                f"turn {turn:4.1f}/{YAW_LIMIT_DEGREES:.0f}  "
                f"eyes {eyes:+.2f}/{EYES_EXTRA_LIMIT}  "
                f"lids {lids:+.2f}/{EYES_EXTRA_LIMIT}  "
                f"all {total:.1f}/{COMBINED_LIMIT}")

    # ---- Background thread ----

    def _loop(self) -> None:
        seconds_per_check = 1.0 / CHECKS_PER_SECOND
        # Failed reads in a row. Used to warn once with advice instead of
        # printing the same line every second.
        failed_reads = 0

        while self._running:
            started = time.monotonic()

            ok, frame = self._camera.read()
            if not ok:
                failed_reads += 1
                # Warn on the 3rd failure (one or two at startup are normal),
                # then only every 30 s.
                if failed_reads == 3 or failed_reads % 30 == 0:
                    logger.warning(
                        "Camera %d sends no images. If it's your iPhone (Continuity Camera), "
                        "turn that off on the iPhone: Settings > General > AirPlay & Continuity, "
                        "then restart the server. Or start the server with BUDDY_CAMERA=1.",
                        self._camera_index,
                    )
                time.sleep(1)
                continue
            if failed_reads >= 3:
                logger.info("Camera %d is sending images again", self._camera_index)
            failed_reads = 0

            # OpenCV stores colours as Blue-Green-Red, MediaPipe wants Red-Green-Blue.
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            # VIDEO mode needs a timestamp in milliseconds that always increases.
            timestamp_ms = int(started * 1000)
            result = self._landmarker.detect_for_video(image, timestamp_ms)

            reading = self._make_reading(result, started)

            with self._lock:
                self._latest = reading
                self._update_away_timer(reading, started)
                if self._keep_preview:
                    self._preview = self._draw_preview(frame, result, reading)

            elapsed = time.monotonic() - started
            time.sleep(max(0.0, seconds_per_check - elapsed))

    def _make_reading(self, result, now: float) -> Reading:
        # No face in the image: you turned away or left the desk.
        if len(result.face_landmarks) == 0:
            return Reading(False, 0.0, 0.0, 0.0, 0.0, looking=False, reason="no face")

        pitch, yaw = _head_angles(result.facial_transformation_matrixes[0])
        blendshapes = result.face_blendshapes[0]
        eyes_down = _average_score(blendshapes, "eyeLookDownLeft", "eyeLookDownRight")
        eyelids = _average_score(blendshapes, "eyeBlinkLeft", "eyeBlinkRight")

        # Still calibrating: collect samples, and count you as looking.
        if not self.is_calibrated():
            self._collect_calibration(pitch, yaw, eyes_down, eyelids, now)
            return Reading(True, pitch, yaw, eyes_down, eyelids, looking=True, reason="calibrating")

        # Compare with your working position.
        # head_down is SIGNED: positive = tilted down (Ben's test showed
        # pitch goes up when looking down). Tilting up gives a negative number
        # and never counts.
        head_down = _angle_difference(pitch, self._base_pitch)
        yaw_off = abs(_angle_difference(yaw, self._base_yaw))
        eyes_extra = eyes_down - self._base_eyes
        lids_extra = eyelids - self._base_lids

        if head_down > HEAD_DOWN_LIMIT_DEGREES:
            reason = "head down"
        elif yaw_off > YAW_LIMIT_DEGREES:
            reason = "head turned"
        elif eyes_extra > EYES_EXTRA_LIMIT:
            reason = "eyes down"
        elif lids_extra > EYES_EXTRA_LIMIT:
            reason = "eyelids down"
        elif _combined_score(head_down, yaw_off, eyes_extra, lids_extra) > COMBINED_LIMIT:
            reason = "several signs"
        else:
            reason = "ok"
        return Reading(True, pitch, yaw, eyes_down, eyelids, looking=(reason == "ok"), reason=reason)

    def _collect_calibration(self, pitch: float, yaw: float, eyes_down: float, eyelids: float, now: float) -> None:
        if self._calibration_started_at is None:
            self._calibration_started_at = now
            logger.info("Calibrating: look at the screen normally for %.0f s", CALIBRATION_SECONDS)
        self._pitch_samples.append(pitch)
        self._yaw_samples.append(yaw)
        self._eyes_samples.append(eyes_down)
        self._lids_samples.append(eyelids)

        if now - self._calibration_started_at >= CALIBRATION_SECONDS:
            # Your working position = the average of everything measured.
            # (Averaging angles this way is fine as long as they stay far
            # from the +-180 wrap point, which a face looking at a screen does.)
            self._base_yaw = sum(self._yaw_samples) / len(self._yaw_samples)
            self._base_eyes = sum(self._eyes_samples) / len(self._eyes_samples)
            self._base_lids = sum(self._lids_samples) / len(self._lids_samples)
            # Set pitch LAST: is_calibrated() checks it, and the other three
            # must already be filled in when it becomes True.
            self._base_pitch = sum(self._pitch_samples) / len(self._pitch_samples)
            logger.info("Calibrated. %s", self.calibration_text())

    def _update_away_timer(self, reading: Reading, now: float) -> None:
        # Called with the lock held.
        if reading.looking:
            return
        # If you were "looking" for longer than the allowed gap, this is a
        # new stretch of looking away, so restart the 2 second count.
        new_stretch = self._last_away_at is None or now - self._last_away_at > GAP_ALLOWED_SECONDS
        if new_stretch:
            self._away_since = now
        self._last_away_at = now

    def _draw_preview(self, frame, result, reading: Reading):
        # Copy so we don't draw on the frame MediaPipe is using.
        picture = frame.copy()
        height, width = picture.shape[0], picture.shape[1]

        # Face points come as fractions of the image size (0 to 1).
        if len(result.face_landmarks) > 0:
            for point in result.face_landmarks[0]:
                x = int(point.x * width)
                y = int(point.y * height)
                cv2.circle(picture, (x, y), 1, (255, 200, 0), -1)

        # Green text when looking, red when not. (Colours are Blue-Green-Red.)
        colour = (0, 200, 0) if reading.looking else (0, 0, 255)
        line1 = (
            f"pitch {reading.pitch:6.1f}  yaw {reading.yaw:6.1f}  "
            f"eyes down {reading.eyes_down:.2f}  eyelids {reading.eyelids:.2f}"
        )
        line2 = f"{'LOOKING' if reading.looking else 'NOT LOOKING'} ({reading.reason})"
        cv2.putText(picture, line1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
        cv2.putText(picture, line2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
        # Your working position, in white, so you can compare.
        cv2.putText(picture, self.calibration_text(), (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return picture

    @staticmethod
    def _download_model_if_missing() -> None:
        if os.path.exists(MODEL_PATH):
            return
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        logger.info("Downloading face model to %s", MODEL_PATH)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
