"""Unit tests for schema validation."""

import pytest
from pydantic import ValidationError

from matrix_nio_mcp.schemas import (
    CreateRoomInput,
    GetMessagesInput,
    SendMessageInput,
    SetPowerLevelInput,
)


def test_send_message_defaults():
    inp = SendMessageInput(room_id="!abc:example.com", body="hello")
    assert inp.format == "plain"
    assert inp.reply_to_event_id is None


def test_get_messages_limit_clamp():
    inp = GetMessagesInput(room_id="!abc:example.com", limit=50)
    assert inp.limit == 50


def test_get_messages_limit_too_high():
    with pytest.raises(ValidationError):
        GetMessagesInput(room_id="!abc:example.com", limit=501)


def test_get_messages_limit_zero():
    with pytest.raises(ValidationError):
        GetMessagesInput(room_id="!abc:example.com", limit=0)


def test_create_room_defaults():
    inp = CreateRoomInput()
    assert inp.encrypted is True
    assert inp.is_public is False
    assert inp.invite == []


def test_set_power_level_bounds():
    inp = SetPowerLevelInput(room_id="!x:s", user_id="@u:s", power_level=100)
    assert inp.power_level == 100

    with pytest.raises(ValidationError):
        SetPowerLevelInput(room_id="!x:s", user_id="@u:s", power_level=101)

    with pytest.raises(ValidationError):
        SetPowerLevelInput(room_id="!x:s", user_id="@u:s", power_level=-1)
