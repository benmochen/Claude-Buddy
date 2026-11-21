# A GET endpoint so you (and later the webcam script) can ask
# "what state is the buddy in right now?"

from fastapi import APIRouter, Depends

from buddy.dependencies import get_buddy_service
from buddy.services.buddy_service import BuddyService

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(service: BuddyService = Depends(get_buddy_service)) -> dict:
    return service.get_status()
