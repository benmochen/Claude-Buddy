# Tests the attention detector on its own, without the server.
# Shows the camera image with your face points and live numbers, and
# prints what the buddy would decide. Press q in the video window to quit.
#
# Run from the laptop folder:   python camera_test.py
# Use another camera:           python camera_test.py 1

import logging
import sys
import time

import cv2

from buddy.detectors.attention_detector import AttentionDetector

# Show the detector's "Calibrating..." and "Calibrated: ..." messages.
logging.basicConfig(level=logging.INFO, format="%(message)s")

# sys.argv is the list of words typed after "python": ["camera_test.py", "1"].
camera_index = 0
if len(sys.argv) > 1:
    camera_index = int(sys.argv[1])

detector = AttentionDetector(camera_index=camera_index, keep_preview=True)
detector.start()

print("Look at the screen normally for the first 3 seconds (calibration).")
print("Then try: phone in your lap, phone at chest height, looking at the keyboard,")
print("turning to a teammate. In the video window: c = recalibrate, q = quit.\n")
last_print = 0.0

try:
    while True:
        # imshow must run on the main thread on macOS, so it's here.
        frame = detector.latest_preview()
        if frame is not None:
            cv2.imshow("Desk buddy camera test (q to quit)", frame)

        # waitKey(30) waits 30 ms for a key and lets the window redraw.
        # & 0xFF keeps only the key code; ord("q") is the code of the q key.
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c"):
            print("\nRecalibrating: look at the screen normally for 3 seconds.\n", flush=True)
            detector.recalibrate()

        # Print the numbers twice per second.
        now = time.monotonic()
        reading = detector.latest_reading()
        if reading is not None and now - last_print >= 0.5:
            distracted = "YES, would yell" if detector.is_distracted() else "no"
            print(
                f"pitch {reading.pitch:6.1f} | yaw {reading.yaw:6.1f} | "
                f"eyes down {reading.eyes_down:.2f} | eyelids {reading.eyelids:.2f} | "
                f"{reading.reason:<12} | distracted: {distracted}",
                flush=True,
            )
            last_print = now
finally:
    # Runs even after Ctrl+C, so the camera light turns off.
    detector.stop()
    cv2.destroyAllWindows()
    # Repeat the working position at the end so it doesn't scroll away.
    print("\n" + detector.calibration_text())
