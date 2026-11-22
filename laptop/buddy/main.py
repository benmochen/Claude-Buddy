# Entry point. uvicorn loads the `app` object from this file.

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from buddy.api import button, camera, hooks, mood, status
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

    # Opens the STM32's serial port (if plugged in) and starts listening for BTN and SLAP.
    get_output().start(on_button=on_board_button, on_slap=on_board_slap)
    yield
    # Closes the serial port.
    get_output().stop()
    # Closes the webcam so its light turns off.
    get_detector().stop()


def _log_button_result(future) -> None:
    # Runs when the button press has been handled.
    try:
        logging.getLogger(__name__).info("STM32 button: %s", future.result())
    except Exception:
        logging.getLogger(__name__).exception("STM32 button press failed")


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


# Addresses that mean "this laptop itself".
LOCAL_CLIENTS = ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def network_can_only_view_face(request, call_next):
    # To let the phone reach the face page, the server listens on the Wi-Fi
    # network (uvicorn --host 0.0.0.0). Then ANY device on that Wi-Fi could
    # call it, and on hackathon Wi-Fi that's a room full of strangers. So
    # other devices may only GET the face page, its files and /status.
    # Everything else (hooks, /slap = undo your files, /button = type into
    # Claude, /mood, /messages, /calibrate) only works from this laptop.
    client = request.client.host if request.client else ""
    if client in LOCAL_CLIENTS:
        return await call_next(request)
    path = request.url.path
    viewing_face = path == "/face" or path == "/status" or path.startswith("/static/")
    if request.method == "GET" and viewing_face:
        return await call_next(request)
    logging.getLogger(__name__).warning("Refused %s %s from %s", request.method, path, client)
    return JSONResponse({"detail": "only the face page is reachable from other devices"}, status_code=403)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/face", include_in_schema=False)
async def face() -> FileResponse:
    # The buddy's face for a phone in the toy: http://<laptop IP>:8765/face
    return FileResponse(STATIC_DIR / "face.html")
