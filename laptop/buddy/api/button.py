# The redo button endpoint.
# For now you "press" it with curl. Later the serial reader calls the same
# service method when the STM32 sends "BTN", so the logic lives in the
# service, not here.

from fastapi import APIRouter, Depends

from buddy.dependencies import get_buddy_service
from buddy.services.buddy_service import BuddyService

router = APIRouter(tags=["button"])


@router.post("/button")
async def press_button(service: BuddyService = Depends(get_buddy_service)) -> dict:
    # Unlike the hooks, this replies with a body, so you can see in the
    # curl output whether the press did anything and why not.
    result = await service.on_button_pressed()
    return {"result": result}


@router.post("/slap")
async def slap(service: BuddyService = Depends(get_buddy_service)) -> dict:
    # Fake a slap on the head without the board: brings Claude Code to the front.
    result = await service.on_slap()
    return {"result": result}
