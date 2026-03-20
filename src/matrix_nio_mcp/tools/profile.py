"""Profile and DM tools."""

from __future__ import annotations

import nio  # type: ignore[import-untyped]

from ..errors import MatrixUserNotFound, raise_for_nio_response
from ..schemas import (
    CreateDMInput,
    DMSummary,
    GetUserProfileInput,
    SetDisplayNameInput,
    UserProfile,
)
from ..session import Session


async def get_user_profile(session: Session, inp: GetUserProfileInput) -> dict:
    resp = await session.client.get_profile(inp.user_id)
    if isinstance(resp, nio.ProfileGetError):
        raise MatrixUserNotFound(f"User not found: {inp.user_id}")
    return UserProfile(
        user_id=inp.user_id,
        display_name=resp.displayname,
        avatar_url=resp.avatar_url,
    ).model_dump()


async def set_display_name(session: Session, inp: SetDisplayNameInput) -> dict:
    resp = await session.client.set_displayname(inp.display_name)
    if isinstance(resp, nio.ProfileSetDisplayNameError):
        raise_for_nio_response(resp)
    return {"success": True}


async def whoami(session: Session) -> dict:
    client = session.client
    return {
        "user_id": client.user_id,
        "device_id": client.device_id,
        "homeserver": client.homeserver,
    }


async def create_dm(session: Session, inp: CreateDMInput) -> dict:
    client = session.client

    # Check if a DM already exists
    for room_id, room in client.rooms.items():
        if room.is_group and len(room.users) == 2 and inp.user_id in room.users:
            return {"room_id": room_id, "created": False}

    resp = await client.room_create(
        is_direct=True,
        invite=[inp.user_id],
        preset=nio.RoomPreset.trusted_private_chat,
        initial_state=[
            {"type": "m.room.encryption", "content": {"algorithm": "m.megolm.v1.aes-sha2"}}
        ],
    )
    if isinstance(resp, nio.RoomCreateError):
        raise_for_nio_response(resp)
    return {"room_id": resp.room_id, "created": True}


async def list_dms(session: Session) -> dict:
    client = session.client
    dms = []
    for room_id, room in client.rooms.items():
        if not room.is_group:
            continue
        other_user = next((u for u in room.users if u != client.user_id), None)
        if not other_user:
            continue
        member = room.users.get(other_user)
        dms.append(
            DMSummary(
                room_id=room_id,
                user_id=other_user,
                display_name=member.display_name if member else None,
                unread_count=room.unread_notifications,
            ).model_dump()
        )
    return {"dms": dms}
