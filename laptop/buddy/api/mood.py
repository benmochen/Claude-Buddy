# Endpoints the web page uses to set the buddy's mood by hand and to
# edit what its LCD says for each mood.

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from buddy.dependencies import get_buddy_service
from buddy.services.buddy_service import BuddyService
from buddy.state import BuddyState

router = APIRouter(tags=["mood"])


class MoodRequest(BaseModel):
    state: BuddyState


@router.post("/mood")
async def set_mood(body: MoodRequest, service: BuddyService = Depends(get_buddy_service)) -> dict:
    try:
        service.set_mood(body.state)
    except ValueError as exc:
        # ANNOYED and YELLING belong to the nag timer, not the web page.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return service.get_status()


@router.get("/messages")
async def get_messages(service: BuddyService = Depends(get_buddy_service)) -> Dict[str, str]:
    return service.get_messages()


@router.put("/messages")
async def update_messages(
    body: Dict[str, str],
    service: BuddyService = Depends(get_buddy_service),
) -> Dict[str, str]:
    try:
        return service.update_messages(body)
    except ValueError as exc:
        # 422 with a sentence the page can show next to the field.
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/messages")
async def reset_messages(service: BuddyService = Depends(get_buddy_service)) -> Dict[str, str]:
    return service.reset_messages()
