# Entry point. uvicorn loads the `app` object from this file.

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from buddy.api import button, camera, hooks, status
from buddy.dependencies import get_detector

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
    yield
    # Closes the webcam so its light turns off.
    get_detector().stop()


app = FastAPI(title="Desk buddy", lifespan=lifespan)
app.include_router(hooks.router)
app.include_router(status.router)
app.include_router(button.router)
app.include_router(camera.router)
