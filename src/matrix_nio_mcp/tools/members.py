"""Membership management tools."""

from __future__ import annotations

import nio  # type: ignore[import-untyped]

from ..errors import MatrixRoomNotFound, raise_for_nio_response
from ..schemas import (
    BanUserInput,
    GetRoomMembersInput,
    InviteUserInput,
    KickUserInput,
    Member,
    SetPowerLevelInput,
    UnbanUserInput,
)
from ..session import Session


async def get_room_members(session: Session, inp: GetRoomMembersInput) -> dict:
    client = session.client
    room = client.rooms.get(inp.room_id)
    if not room:
        raise MatrixRoomNotFound(f"Room not found: {inp.room_id}")

    pl_content: dict = {}
    for ev in room.state_events.get("m.room.power_levels", {}).values():
        pl_content = ev.get("content", {})
        break
    user_power: dict = pl_content.get("users", {})

    members = []
    for user_id, member in room.users.items():
        if inp.membership and member.membership != inp.membership:
            continue
        members.append(
            Member(
                user_id=user_id,
                display_name=member.display_name,
                avatar_url=member.avatar_url,
                membership=member.membership,
                power_level=user_power.get(user_id, pl_content.get("users_default", 0)),
            ).model_dump()
        )
    return {"members": members}


async def invite_user(session: Session, inp: InviteUserInput) -> dict:
    resp = await session.client.room_invite(inp.room_id, inp.user_id)
    if isinstance(resp, nio.RoomInviteError):
        raise_for_nio_response(resp)
    return {"success": True}


async def kick_user(session: Session, inp: KickUserInput) -> dict:
    resp = await session.client.room_kick(inp.room_id, inp.user_id, reason=inp.reason)
    if isinstance(resp, nio.RoomKickError):
        raise_for_nio_response(resp)
    return {"success": True}


async def ban_user(session: Session, inp: BanUserInput) -> dict:
    resp = await session.client.room_ban(inp.room_id, inp.user_id, reason=inp.reason)
    if isinstance(resp, nio.RoomBanError):
        raise_for_nio_response(resp)
    return {"success": True}


async def unban_user(session: Session, inp: UnbanUserInput) -> dict:
    resp = await session.client.room_unban(inp.room_id, inp.user_id)
    if isinstance(resp, nio.RoomUnbanError):
        raise_for_nio_response(resp)
    return {"success": True}


async def set_power_level(session: Session, inp: SetPowerLevelInput) -> dict:
    client = session.client
    room = client.rooms.get(inp.room_id)
    if not room:
        raise MatrixRoomNotFound(f"Room not found: {inp.room_id}")

    pl_content: dict = {}
    for ev in room.state_events.get("m.room.power_levels", {}).values():
        pl_content = dict(ev.get("content", {}))
        break

    users = dict(pl_content.get("users", {}))
    users[inp.user_id] = inp.power_level
    pl_content["users"] = users

    resp = await client.room_put_state(inp.room_id, "m.room.power_levels", pl_content)
    if isinstance(resp, nio.RoomPutStateError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}
