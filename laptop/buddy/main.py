# Entry point. uvicorn loads the `app` object from this file.

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from buddy.api import hooks, mood, status

# INFO shows state changes. Change to logging.DEBUG to also see which
# fields each hook sent (names only, never values).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Desk buddy")
app.include_router(hooks.router)
app.include_router(status.router)
app.include_router(mood.router)

# The mood page: open http://127.0.0.1:8765/ in a browser.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_page(request, call_next):
    # Make the browser check for a newer copy on every load (a cheap 304 when
    # nothing changed), so an updated page never shows up as the old one.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
