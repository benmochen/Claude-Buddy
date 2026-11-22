# The phone face: a web page (static/face.html) that draws the buddy's eyes,
# and the small JSON it asks for 3 times a second.
# These two are the ONLY routes other devices (the phone) may use; see the
# "local_only" rule in main.py.

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from buddy.dependencies import get_buddy_service
from buddy.services.buddy_service import BuddyService

router = APIRouter(tags=["face"])

# Where face.html lives: buddy/static/face.html
FACE_PAGE = Path(__file__).parent.parent / "static" / "face.html"


@router.get("/face", include_in_schema=False)
async def face_page() -> FileResponse:
    return FileResponse(FACE_PAGE)


@router.get("/face/state")
async def face_state(service: BuddyService = Depends(get_buddy_service)) -> dict:
    # Only what the eyes need, nothing else (the phone may be on shared Wi-Fi).
    return service.get_face_state()
