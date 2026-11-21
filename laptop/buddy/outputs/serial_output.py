# Shows the buddy's state on the STM32's display, over the USB cable.
# Same show(state, text) method as ConsoleOutput, so BuddyService doesn't
# know or care which one it has. It also still prints to the terminal.
#
# The board appears on the Mac as /dev/cu.usbmodemXXXX (the ST-LINK's
# "virtual COM port"). Messages are lines of text ending in "\n":
#   laptop -> board: F:IDLE, F:WORK, F:DONE, F:NEED, F:MAD (which face),
#                    T:<text> (status text, max 16 chars)
#   board -> laptop: BTN (the big undo button was pressed),
#                    SLAP:<n> (the head was slapped, n = strength in milli-g),
#                    ERR:ACCEL (the accelerometer did not start)

import logging
import threading
from typing import Callable, Optional

import serial                      # pyserial: talks to serial ports
from serial.tools import list_ports

from buddy.outputs.console_output import ConsoleOutput
from buddy.state import BuddyState

logger = logging.getLogger(__name__)

# Must match huart1.Init.BaudRate in the firmware (usart.c).
BAUD_RATE = 115200

# Which face each state shows. The board maps these to its 4 faces:
# IDLE/WORK = normal, DONE = happy, NEED = sad, MAD = ouch.
FACE_FOR_STATE = {
    BuddyState.IDLE: "F:IDLE",
    BuddyState.WORKING: "F:WORK",
    BuddyState.DONE: "F:DONE",
    BuddyState.NEEDS_YOU: "F:NEED",
    BuddyState.ANNOYED: "F:MAD",
    BuddyState.YELLING: "F:MAD",
}


def find_board_port() -> Optional[str]:
    # Looks through the Mac's serial ports for one named like
    # /dev/cu.usbmodem... (that's how macOS names the ST-LINK).
    # Returns None if the board isn't plugged in.
    for port in list_ports.comports():
        if "usbmodem" in port.device and port.device.startswith("/dev/cu."):
            return port.device
    return None


class SerialOutput:
    def __init__(self, port: Optional[str]) -> None:
        # port: e.g. "/dev/cu.usbmodem1103", or None to find it automatically.
        self._port_name = port
        self._console = ConsoleOutput()           # keep printing to the terminal too
        self._serial: Optional[serial.Serial] = None
        # The reader thread and show() both touch self._serial; the lock
        # stops one from closing it while the other is using it.
        self._lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self._running = False

    def start(self, on_button: Callable[[], None], on_slap: Callable[[], None]) -> None:
        # Called once when the server starts (main.py lifespan).
        # on_button: function to call when the board sends "BTN".
        # on_slap:   function to call when the board sends "SLAP:<n>".
        port_name = self._port_name or find_board_port()
        if port_name is None:
            # Shortcut: no retry. Plug the board in, then restart the server.
            logger.warning("STM32 not found (no /dev/cu.usbmodem*). Terminal only.")
            return
        try:
            # timeout=0.5: readline() gives up after 0.5 s with no data, so the
            # reader thread can notice when the server is shutting down.
            self._serial = serial.Serial(port_name, BAUD_RATE, timeout=0.5)
        except serial.SerialException:
            logger.exception("Could not open %s. Terminal only.", port_name)
            return
        logger.info("Connected to STM32 on %s", port_name)

        self._running = True
        # daemon=True: the thread never stops the Python process from exiting.
        self._reader = threading.Thread(
            target=self._read_loop, args=(on_button, on_slap), daemon=True
        )
        self._reader.start()

    def stop(self) -> None:
        # Called when the server stops (Ctrl+C).
        self._running = False
        if self._reader is not None:
            self._reader.join(timeout=1.0)     # wait for the thread to see _running
        with self._lock:
            if self._serial is not None:
                self._serial.close()
                self._serial = None

    def show(self, state: BuddyState, text: str) -> None:
        # Called by BuddyService on every state change.
        self._console.show(state, text)
        self._send(FACE_FOR_STATE[state])
        self._send("T:" + text)

    def is_connected(self) -> bool:
        # True while the board's serial port is open. Used by the Speaker to
        # decide between the toy's speaker and the laptop's.
        return self._serial is not None

    def send_line(self, line: str) -> None:
        # Send one protocol line, for example "S:yay" (play a voice clip).
        self._send(line)

    def _send(self, line: str) -> None:
        with self._lock:
            if self._serial is None:
                return                          # board not connected
            try:
                # errors="replace": a non-ASCII character becomes "?" instead of crashing.
                self._serial.write((line + "\n").encode("ascii", errors="replace"))
            except serial.SerialException:
                # Usually the USB cable was pulled. Shortcut: no reconnect,
                # restart the server after plugging it back in.
                logger.exception("Lost the STM32. Terminal only from now on.")
                self._serial.close()
                self._serial = None
                self._running = False

    def _read_loop(self, on_button: Callable[[], None], on_slap: Callable[[], None]) -> None:
        # Runs in its own thread: waits for lines from the board.
        while self._running:
            with self._lock:
                port = self._serial
            if port is None:
                return                          # disconnected or stopped
            try:
                raw = port.readline()           # bytes up to "\n", or b"" after 0.5 s
            except serial.SerialException:
                logger.exception("Lost the STM32 while reading.")
                return
            message = raw.decode("ascii", errors="replace").strip()
            if message == "BTN":
                logger.info("Button pressed on the STM32")
                on_button()
            elif message.startswith("SLAP:"):
                # The number is the slap strength (1000 = 1 g). Logged so you
                # can tune SLAP_THRESHOLD_MG in the firmware's accel.c.
                logger.info("Head slapped on the STM32 (strength %s mg)", message[5:])
                on_slap()
            elif message.startswith("ERR:"):
                logger.warning("STM32 reported a problem: %s", message[4:])
            elif message:
                # Anything else (for example PONG) is only interesting when debugging.
                logger.debug("STM32 sent %r", message)
