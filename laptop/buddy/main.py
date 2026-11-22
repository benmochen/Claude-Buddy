# Entry point. uvicorn loads the `app` object from this file.

import asyncio
import logging
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from buddy.api import button, camera, face, hooks, mood, status
from buddy.dependencies import get_buddy_service, get_detector, get_output

# INFO shows state changes. Change to logging.DEBUG to also see which
# fields each hook sent (names only, never values).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# lifespan: code before `yield` runs when the server starts, code after it
# when the server stops (Ctrl+C). Like @PostConstruct / @PreDestroy in Spring.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Opens the webcam. Runs on the main thread, which macOS needs for the
    # camera permission popup. Calibration starts as soon as it sees a face,
    # so look at the screen while the server starts.
    get_detector().start()

    # The serial reader runs in its own thread, but on_button_pressed() is an
    # async method that must run on FastAPI's event loop. run_coroutine_threadsafe
    # hands it over from the thread to the loop.
    loop = asyncio.get_running_loop()

    def on_board_button() -> None:
        future = asyncio.run_coroutine_threadsafe(
            get_buddy_service().on_button_pressed(), loop
        )
        # Log the result ("sent", "ignored: ...") once it finishes.
        future.add_done_callback(_log_button_result)

    def on_board_slap() -> None:
        # Same hand-over as the button, for "SLAP" from the accelerometer.
        future = asyncio.run_coroutine_threadsafe(get_buddy_service().on_slap(), loop)
        future.add_done_callback(_log_slap_result)

    def on_board_knock() -> None:
        # Same hand-over, for "KNOCK" (knock-knock on the head).
        future = asyncio.run_coroutine_threadsafe(get_buddy_service().on_knock(), loop)
        future.add_done_callback(_log_knock_result)

    def on_board_maybe() -> None:
        # Same hand-over, for "MAYBE" (unsure tap: the buddy asks "New chat?").
        future = asyncio.run_coroutine_threadsafe(get_buddy_service().on_maybe(), loop)
        future.add_done_callback(_log_knock_result)

    # Opens the STM32's serial port (if plugged in) and starts listening for
    # BTN, SLAP, KNOCK and MAYBE.
    get_output().start(on_button=on_board_button, on_slap=on_board_slap,
                       on_knock=on_board_knock, on_maybe=on_board_maybe)
    # Print the address to type on the phone.
    logging.getLogger(__name__).info(
        "Phone face: open http://%s:8765/face on the phone (same Wi-Fi or hotspot)",
        _lan_address(),
    )
    # BUDDY_SHOW_CAMERA=1: print what the camera sees twice a second.
    camera_printer = None
    if os.environ.get("BUDDY_SHOW_CAMERA") == "1":
        camera_printer = asyncio.create_task(_print_camera_forever())
    yield
    if camera_printer is not None:
        camera_printer.cancel()                # stop printing when the server stops
    # Closes the serial port.
    get_output().stop()
    # Closes the webcam so its light turns off.
    get_detector().stop()


async def _print_camera_forever() -> None:
    # Prints the camera's verdict every 0.5 s, for example:
    #   [camera 09:41:07] LOOKING      ok            down  +2.1/10  turn  1.0/30  eyes +0.02/0.35  lids +0.05/0.35
    #   [camera 09:41:08] NOT LOOKING  head down     down +14.3/10  turn  2.0/30  eyes +0.10/0.35  lids +0.30/0.35
    # "ok" or the reason comes from the latest frame ("head down", "head
    # turned", "eyes down", "eyelids down", "no face", "calibrating").
    detector = get_detector()
    while True:
        if detector.is_looking_now():
            verdict = "LOOKING    "
        else:
            verdict = "NOT LOOKING"
        clock = time.strftime("%H:%M:%S")
        reason = detector.latest_reason()
        # The measured numbers next to their limits (empty without a face).
        numbers = detector.latest_numbers()
        print(f"[camera {clock}] {verdict}  {reason:<13} {numbers}", flush=True)
        await asyncio.sleep(0.5)


def _log_button_result(future) -> None:
    # Runs when the button press has been handled.
    try:
        logging.getLogger(__name__).info("STM32 button: %s", future.result())
    except Exception:
        logging.getLogger(__name__).exception("STM32 button press failed")


def _lan_address() -> str:
    # The laptop's address on the Wi-Fi, for example 192.168.1.23.
    # Connecting a UDP socket sends no data; it only makes macOS pick the
    # network interface it would use, and tells us that interface's address.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return "<laptop address>"           # no network at all
    finally:
        probe.close()


def _log_knock_result(future) -> None:
    # Runs when the knock-knock has been handled ("new chat" or "ignored: ...").
    try:
        logging.getLogger(__name__).info("STM32 knock-knock: %s", future.result())
    except Exception:
        logging.getLogger(__name__).exception("STM32 knock-knock failed")


def _log_slap_result(future) -> None:
    # Runs when the slap has been handled ("focused" or "failed: ...").
    try:
        logging.getLogger(__name__).info("STM32 slap: %s", future.result())
    except Exception:
        logging.getLogger(__name__).exception("STM32 slap failed")


app = FastAPI(title="Desk buddy", lifespan=lifespan)
app.include_router(hooks.router)
app.include_router(status.router)
app.include_router(button.router)
app.include_router(camera.router)
app.include_router(mood.router)
app.include_router(face.router)

# The only things other devices (the phone) may open. Everything else (hooks,
# /slap, /button, the mood page...) only works from this laptop, because with
# --host 0.0.0.0 anyone on the same Wi-Fi could otherwise undo your files or
# type into Claude.
PUBLIC_PATHS = ("/face", "/face/state", "/face/sounds")
# Plus the voice clips: /face/sounds/<name>.mp3
PUBLIC_PREFIX = "/face/sounds/"
LOCAL_ADDRESSES = ("127.0.0.1", "::1")


@app.middleware("http")
async def local_only(request: Request, call_next):
    # request.client.host is the address the request came from.
    client = request.client.host if request.client else ""
    is_local = client in LOCAL_ADDRESSES
    path = request.url.path
    is_public_path = path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIX)
    is_public = request.method == "GET" and is_public_path
    if not is_local and not is_public:
        # 403 = forbidden. Nothing in the app runs for this request.
        return JSONResponse({"detail": "only allowed from the laptop itself"}, status_code=403)
    return await call_next(request)

# The mood page: open http://127.0.0.1:8765/ in a browser.
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_page(request, call_next):
    # Make the browser check for a newer copy on every load (a cheap 304 when
    # nothing changed), so an updated page never shows up as the old one.
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path == "/face" or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
