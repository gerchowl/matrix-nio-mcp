"""Room management tools."""

from __future__ import annotations

from typing import Any

import nio  # type: ignore[import-untyped]

from ..errors import raise_for_nio_response
from ..schemas import (
    CreateRoomInput,
    GetRoomInput,
    GetRoomStateInput,
    JoinRoomInput,
    LeaveRoomInput,
    PowerLevels,
    RoomDetail,
    RoomSummary,
    SendStateEventInput,
    SetRoomNameInput,
    SetRoomTopicInput,
    StateEvent,
)
from ..session import Session


def _power_levels_from_content(content: dict) -> PowerLevels:
    return PowerLevels(
        users_default=content.get("users_default", 0),
        events_default=content.get("events_default", 0),
        state_default=content.get("state_default", 50),
        ban=content.get("ban", 50),
        kick=content.get("kick", 50),
        redact=content.get("redact", 50),
        invite=content.get("invite", 0),
        users=content.get("users", {}),
        events=content.get("events", {}),
    )


async def list_rooms(session: Session) -> dict:
    client = session.client
    summaries = []
    for room_id, room in client.rooms.items():
        summaries.append(
            RoomSummary(
                room_id=room_id,
                display_name=room.display_name or room_id,
                topic=room.topic,
                member_count=room.member_count,
                unread_count=room.unread_notifications,
                is_encrypted=room.encrypted,
                is_direct=room.is_group,
            ).model_dump()
        )
    return {"rooms": summaries}


async def get_room(session: Session, inp: GetRoomInput) -> dict:
    client = session.client
    room = client.rooms.get(inp.room_id)
    if not room:
        from ..errors import MatrixRoomNotFound
        raise MatrixRoomNotFound(f"Room not found: {inp.room_id}")

    pl_content: dict = {}
    for ev in room.state_events.get("m.room.power_levels", {}).values():
        pl_content = ev.get("content", {})
        break

    detail = RoomDetail(
        room_id=inp.room_id,
        display_name=room.display_name or inp.room_id,
        canonical_alias=room.canonical_alias,
        aliases=list(room.aliases),
        topic=room.topic,
        avatar_url=room.gen_avatar_url,
        member_count=room.member_count,
        is_encrypted=room.encrypted,
        encryption_algorithm=room.encryption if room.encrypted else None,
        is_direct=room.is_group,
        creation_ts=room.create_time or 0,
        power_levels=_power_levels_from_content(pl_content),
    )
    return detail.model_dump()


async def create_room(session: Session, inp: CreateRoomInput) -> dict:
    preset_map = {
        "private_chat": nio.RoomPreset.private_chat,
        "public_chat": nio.RoomPreset.public_chat,
        "trusted_private_chat": nio.RoomPreset.trusted_private_chat,
    }
    preset = preset_map.get(inp.preset or "", None) if inp.preset else None

    initial_state: list[dict] = []
    if inp.encrypted:
        initial_state.append({
            "type": "m.room.encryption",
            "content": {"algorithm": "m.megolm.v1.aes-sha2"},
        })

    resp = await session.client.room_create(
        name=inp.name,
        alias=inp.alias,
        topic=inp.topic,
        is_direct=inp.is_direct,
        visibility=nio.RoomVisibility.public if inp.is_public else nio.RoomVisibility.private,
        preset=preset,
        invite=inp.invite,
        initial_state=initial_state,
    )
    if isinstance(resp, nio.RoomCreateError):
        raise_for_nio_response(resp)
    return {"room_id": resp.room_id}


async def join_room(session: Session, inp: JoinRoomInput) -> dict:
    kwargs: dict[str, Any] = {}
    if inp.server_hint:
        kwargs["server_name"] = [inp.server_hint]

    resp = await session.client.join(inp.room_id_or_alias, **kwargs)
    if isinstance(resp, nio.JoinError):
        raise_for_nio_response(resp)
    return {"room_id": resp.room_id}


async def leave_room(session: Session, inp: LeaveRoomInput) -> dict:
    resp = await session.client.room_leave(inp.room_id)
    if isinstance(resp, nio.RoomLeaveError):
        raise_for_nio_response(resp)
    return {"success": True}


async def set_room_name(session: Session, inp: SetRoomNameInput) -> dict:
    resp = await session.client.room_put_state(
        inp.room_id, "m.room.name", {"name": inp.name}
    )
    if isinstance(resp, nio.RoomPutStateError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}


async def set_room_topic(session: Session, inp: SetRoomTopicInput) -> dict:
    resp = await session.client.room_put_state(
        inp.room_id, "m.room.topic", {"topic": inp.topic}
    )
    if isinstance(resp, nio.RoomPutStateError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}


async def get_room_state(session: Session, inp: GetRoomStateInput) -> dict:
    resp = await session.client.room_get_state(inp.room_id)
    if isinstance(resp, nio.RoomGetStateError):
        raise_for_nio_response(resp)

    events = [
        StateEvent(
            type=ev.get("type", ""),
            state_key=ev.get("state_key", ""),
            content=ev.get("content", {}),
            sender=ev.get("sender", ""),
            origin_server_ts=ev.get("origin_server_ts", 0),
        ).model_dump()
        for ev in resp.events
        if inp.event_type is None or ev.get("type") == inp.event_type
    ]
    return {"state_events": events}


async def send_state_event(session: Session, inp: SendStateEventInput) -> dict:
    resp = await session.client.room_put_state(
        inp.room_id, inp.event_type, inp.content, state_key=inp.state_key
    )
    if isinstance(resp, nio.RoomPutStateError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}


