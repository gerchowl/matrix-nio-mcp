"""Integration tests — room management tools (requires Synapse)."""

from __future__ import annotations

import pytest

from matrix_nio_mcp.schemas import (
    BanUserInput,
    CreateRoomInput,
    GetRoomInput,
    GetRoomMembersInput,
    InviteUserInput,
    KickUserInput,
    LeaveRoomInput,
    SetRoomNameInput,
    SetRoomTopicInput,
    UnbanUserInput,
)
from matrix_nio_mcp.tools import members, rooms


@pytest.mark.asyncio
async def test_create_room(matrix_session):
    result = await rooms.create_room(
        matrix_session,
        CreateRoomInput(name="integration-create-test", encrypted=False),
    )
    assert "room_id" in result
    assert result["room_id"].startswith("!")


@pytest.mark.asyncio
async def test_get_room(matrix_session):
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="integration-get-test", encrypted=False)
    )
    room_id = created["room_id"]

    detail = await rooms.get_room(matrix_session, GetRoomInput(room_id=room_id))
    assert detail["room_id"] == room_id
    assert "power_levels" in detail


@pytest.mark.asyncio
async def test_list_rooms(matrix_session):
    await rooms.create_room(matrix_session, CreateRoomInput(name="list-rooms-test", encrypted=False))
    result = await rooms.list_rooms(matrix_session)
    assert "rooms" in result
    assert len(result["rooms"]) >= 1


@pytest.mark.asyncio
async def test_set_room_name_and_topic(matrix_session):
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="rename-me", encrypted=False)
    )
    room_id = created["room_id"]

    r1 = await rooms.set_room_name(matrix_session, SetRoomNameInput(room_id=room_id, name="new-name"))
    assert "event_id" in r1

    r2 = await rooms.set_room_topic(matrix_session, SetRoomTopicInput(room_id=room_id, topic="new topic"))
    assert "event_id" in r2


@pytest.mark.asyncio
async def test_invite_and_kick(matrix_session, second_user):
    second_user_id, _ = second_user
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="invite-kick-test", encrypted=False)
    )
    room_id = created["room_id"]

    invite_result = await members.invite_user(
        matrix_session, InviteUserInput(room_id=room_id, user_id=second_user_id)
    )
    assert invite_result.get("success") or "event_id" in invite_result or invite_result == {}

    kick_result = await members.kick_user(
        matrix_session,
        KickUserInput(room_id=room_id, user_id=second_user_id, reason="test kick"),
    )
    assert kick_result.get("success") or kick_result == {}


@pytest.mark.asyncio
async def test_ban_and_unban(matrix_session, second_user):
    second_user_id, _ = second_user
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="ban-unban-test", encrypted=False)
    )
    room_id = created["room_id"]

    await members.ban_user(
        matrix_session,
        BanUserInput(room_id=room_id, user_id=second_user_id, reason="test ban"),
    )
    await members.unban_user(
        matrix_session,
        UnbanUserInput(room_id=room_id, user_id=second_user_id),
    )


@pytest.mark.asyncio
async def test_get_room_members(matrix_session):
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="members-test", encrypted=False)
    )
    room_id = created["room_id"]

    result = await members.get_room_members(
        matrix_session, GetRoomMembersInput(room_id=room_id)
    )
    assert "members" in result
    assert len(result["members"]) >= 1


@pytest.mark.asyncio
async def test_leave_room(matrix_session):
    created = await rooms.create_room(
        matrix_session, CreateRoomInput(name="leave-test", encrypted=False)
    )
    room_id = created["room_id"]

    result = await rooms.leave_room(matrix_session, LeaveRoomInput(room_id=room_id))
    assert result.get("success") is True
