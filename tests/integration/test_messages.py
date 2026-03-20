"""Integration tests — messaging tools (requires Synapse)."""

from __future__ import annotations

import pytest

from matrix_nio_mcp.schemas import (
    CreateRoomInput,
    GetMessagesInput,
    RedactEventInput,
    SearchMessagesInput,
    SendMessageInput,
    SendReactionInput,
)
from matrix_nio_mcp.tools import messages, rooms


@pytest.mark.asyncio
async def test_send_and_receive_message(matrix_session):
    # Create an unencrypted room for simplicity
    room = await rooms.create_room(matrix_session, CreateRoomInput(name="test-messages", encrypted=False))
    room_id = room["room_id"]

    result = await messages.send_message(
        matrix_session,
        SendMessageInput(room_id=room_id, body="hello from integration test"),
    )
    assert "event_id" in result
    event_id = result["event_id"]
    assert event_id.startswith("$")


@pytest.mark.asyncio
async def test_get_messages(matrix_session):
    room = await rooms.create_room(matrix_session, CreateRoomInput(name="test-get-msgs", encrypted=False))
    room_id = room["room_id"]

    # Send a couple of messages
    for i in range(3):
        await messages.send_message(
            matrix_session,
            SendMessageInput(room_id=room_id, body=f"message {i}"),
        )

    result = await messages.get_messages(matrix_session, GetMessagesInput(room_id=room_id, limit=10))
    assert "messages" in result
    assert len(result["messages"]) >= 3


@pytest.mark.asyncio
async def test_send_reaction(matrix_session):
    room = await rooms.create_room(matrix_session, CreateRoomInput(name="test-reactions", encrypted=False))
    room_id = room["room_id"]

    msg = await messages.send_message(
        matrix_session,
        SendMessageInput(room_id=room_id, body="react to me"),
    )
    reaction = await messages.send_reaction(
        matrix_session,
        SendReactionInput(room_id=room_id, event_id=msg["event_id"], reaction="👍"),
    )
    assert "event_id" in reaction


@pytest.mark.asyncio
async def test_redact_message(matrix_session):
    room = await rooms.create_room(matrix_session, CreateRoomInput(name="test-redact", encrypted=False))
    room_id = room["room_id"]

    msg = await messages.send_message(
        matrix_session,
        SendMessageInput(room_id=room_id, body="delete me"),
    )
    result = await messages.redact_event(
        matrix_session,
        RedactEventInput(room_id=room_id, event_id=msg["event_id"], reason="test redaction"),
    )
    assert "event_id" in result


@pytest.mark.asyncio
async def test_search_messages(matrix_session):
    room = await rooms.create_room(
        matrix_session, CreateRoomInput(name="test-search", encrypted=False)
    )
    room_id = room["room_id"]

    await messages.send_message(
        matrix_session,
        SendMessageInput(room_id=room_id, body="unique-search-term-xyz"),
    )

    result = await messages.search_messages(
        matrix_session,
        SearchMessagesInput(query="unique-search-term-xyz", room_ids=[room_id]),
    )
    assert "results" in result
