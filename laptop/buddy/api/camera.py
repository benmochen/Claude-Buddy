# Camera endpoints. For now just recalibration: run it (with curl) while
# sitting the way you'll sit during the demo, looking at the screen.

from fastapi import APIRouter

from buddy.dependencies import get_detector

router = APIRouter(tags=["camera"])


@router.post("/calibrate")
async def calibrate() -> dict:
    get_detector().recalibrate()
    return {"result": "calibrating: look at the screen normally for 3 seconds"}
