# Builds the one BuddyService the whole app shares.
# Routes ask for it with Depends(get_buddy_service), FastAPI's version of
# Spring injecting a singleton @Service bean into a controller.

from buddy.outputs.console_output import ConsoleOutput
from buddy.services.buddy_service import BuddyService

# Created once, when this module is first imported. There must be exactly
# one, because the buddy's state lives inside it.
_buddy_service = BuddyService(output=ConsoleOutput())


def get_buddy_service() -> BuddyService:
    return _buddy_service
