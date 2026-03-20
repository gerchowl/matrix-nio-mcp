"""Matrix Spaces tools."""

from __future__ import annotations

from typing import Any

import nio  # type: ignore[import-untyped]

from ..errors import raise_for_nio_response
from ..schemas import AddRoomToSpaceInput, ListSpaceChildrenInput, SpaceChild
from ..session import Session


async def list_space_children(session: Session, inp: ListSpaceChildrenInput) -> dict:
    resp = await session.client.room_get_state(inp.space_room_id)
    if isinstance(resp, nio.RoomGetStateError):
        raise_for_nio_response(resp)

    children = []
    for ev in resp.events:
        if ev.get("type") != "m.space.child":
            continue
        child_id = ev.get("state_key", "")
        room = session.client.rooms.get(child_id)
        children.append(
            SpaceChild(
                room_id=child_id,
                display_name=room.display_name if room else None,
                topic=room.topic if room else None,
                member_count=room.member_count if room else 0,
                is_space=bool(room and room.room_type == "m.space") if room else False,
            ).model_dump()
        )
    return {"children": children}


async def add_room_to_space(session: Session, inp: AddRoomToSpaceInput) -> dict:
    content: dict[str, Any] = {
        "via": [session.client.homeserver.replace("https://", "").replace("http://", "")],
        "suggested": inp.suggested,
    }
    resp = await session.client.room_put_state(
        inp.space_room_id,
        "m.space.child",
        content,
        state_key=inp.child_room_id,
    )
    if isinstance(resp, nio.RoomPutStateError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}
