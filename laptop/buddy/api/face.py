# The phone face: a web page (static/face.html) that draws the buddy's eyes
# and plays its voice, the small JSON it asks for 3 times a second, and the
# voice clips themselves.
# These are the ONLY routes other devices (the phone) may use; see the
# "local_only" rule in main.py.

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from buddy.dependencies import get_buddy_service, get_phone_audio
from buddy.outputs.phone_audio import PhoneAudio
from buddy.outputs.speaker import SOUNDS_DIR
from buddy.services.buddy_service import BuddyService

router = APIRouter(tags=["face"])

# Where face.html lives: buddy/static/face.html
FACE_PAGE = Path(__file__).parent.parent / "static" / "face.html"


def _clip_names() -> List[str]:
    # Names of all recorded voice lines, e.g. ["annoyed", "done", ...].
    names: List[str] = []
    # Reads buddy/sounds/ again on every call, so the phone can download a newly added .mp3 right away.
    for path in sorted(SOUNDS_DIR.glob("*.mp3")):
        names.append(path.stem)
    return names


# The phone opens http://<laptop IP>:8765/face (the "Phone face:" log line at startup gives it).
# Reachable from the phone only with uvicorn --host 0.0.0.0; local_only lets it GET this page.
@router.get("/face", include_in_schema=False)
async def face_page() -> FileResponse:
    return FileResponse(FACE_PAGE)


@router.get("/face/state")
async def face_state(
    audio: int = 0,
    service: BuddyService = Depends(get_buddy_service),
    phone: PhoneAudio = Depends(get_phone_audio),
) -> dict:
    # audio=1: the page has sound turned on, so the voice goes to the phone.
    if audio == 1:
        phone.mark_seen()
    # Only what the eyes and the voice need, nothing else (the phone may be on
    # shared Wi-Fi).
    answer = service.get_face_state()
    # Adds sound_id (a counter, +1 per order) and sound (clip name, null = stop); the page acts only when sound_id changes.
    answer.update(phone.snapshot())
    return answer


# GET, not POST: the phone may only GET (main.py local_only). face.html calls it after the sound-on tap.
@router.get("/face/sounds")
async def face_sounds() -> dict:
    # The list of clips, so the page can download them all once in advance.
    return {"clips": _clip_names()}


@router.get("/face/sounds/{file_name}", include_in_schema=False)
async def face_sound_file(file_name: str) -> FileResponse:
    # One clip, e.g. /face/sounds/yay_3.mp3. Only names from the list above are
    # served, so a request like "../../secret" can never reach another file.
    if not file_name.endswith(".mp3") or file_name[:-4] not in _clip_names():
        raise HTTPException(status_code=404, detail="no such clip")
    return FileResponse(SOUNDS_DIR / file_name, media_type="audio/mpeg")
