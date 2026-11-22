# Endpoints that Claude Code's hooks POST to.
# Each one: read the JSON Claude Code sends, call the service, reply 204.

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, Response

from buddy.dependencies import get_buddy_service
from buddy.services.buddy_service import BuddyService

logger = logging.getLogger(__name__)

# prefix means every route below starts with /hooks
router = APIRouter(prefix="/hooks", tags=["hooks"])


def _log_payload(event_name: str, payload: Dict[str, Any]) -> None:
    # Log only the field NAMES, never the values: the payload contains
    # your prompt and Claude's reply, which can contain API keys.
    field_names = sorted(payload.keys())
    logger.debug("%s hook received, fields: %s", event_name, field_names)


# status_code=204 means "success, no body". Claude Code treats a 2xx with
# an empty body as "hook ran fine, nothing to change". A body would be
# parsed as instructions for Claude Code, which we don't want.

@router.post("/prompt-submit", status_code=204)
async def prompt_submit(
    payload: Dict[str, Any] = Body(...),   # the raw JSON body as a dict
    service: BuddyService = Depends(get_buddy_service),
) -> Response:
    _log_payload("UserPromptSubmit", payload)
    service.on_prompt_submitted()
    return Response(status_code=204)


@router.post("/stop", status_code=204)
async def stop(
    payload: Dict[str, Any] = Body(...),
    service: BuddyService = Depends(get_buddy_service),
) -> Response:
    _log_payload("Stop", payload)
    # .get() returns None instead of crashing if the field is missing.
    last_message = payload.get("last_assistant_message")
    service.on_claude_finished(last_message)
    return Response(status_code=204)


@router.post("/notification", status_code=204)
async def notification(
    payload: Dict[str, Any] = Body(...),
    service: BuddyService = Depends(get_buddy_service),
) -> Response:
    _log_payload("Notification", payload)
    service.on_needs_input()
    return Response(status_code=204)


@router.post("/pre-tool-use", status_code=204)
async def pre_tool_use(
    payload: Dict[str, Any] = Body(...),
    service: BuddyService = Depends(get_buddy_service),
) -> Response:
    # Fires just before Claude's Edit, Write, MultiEdit or NotebookEdit tool
    # runs (the matcher in .claude/settings.json picks those tools). We only
    # read the file path; the new file content in the payload is ignored.
    _log_payload("PreToolUse", payload)
    tool_input = payload.get("tool_input") or {}
    # Edit/Write/MultiEdit call it file_path, NotebookEdit calls it notebook_path.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if isinstance(file_path, str):
        service.on_before_edit(file_path)
    # Always 204 with no body: "go ahead", never blocks Claude's edit.
    return Response(status_code=204)


@router.post("/post-tool-use", status_code=204)
async def post_tool_use(
    payload: Dict[str, Any] = Body(...),
    service: BuddyService = Depends(get_buddy_service),
) -> Response:
    # Fires after every tool Claude runs. Only used to notice that a
    # permission prompt was answered (Claude carried on), so the buddy stops
    # nagging about it. Nothing in the payload is read.
    _log_payload("PostToolUse", payload)
    service.on_tool_finished()
    return Response(status_code=204)
