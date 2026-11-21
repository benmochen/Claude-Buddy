# Entry point. uvicorn loads the `app` object from this file.

import logging

from fastapi import FastAPI

from buddy.api import hooks, status

# INFO shows state changes. Change to logging.DEBUG to also see which
# fields each hook sent (names only, never values).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Desk buddy")
app.include_router(hooks.router)
app.include_router(status.router)
