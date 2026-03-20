"""Pydantic I/O models for all MCP tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared leaf types
# ---------------------------------------------------------------------------

class Message(BaseModel):
    event_id: str
    sender: str
    timestamp: int
    type: str  # "text" | "notice" | "image" | "file" | "redacted" | ...
    body: str
    formatted_body: str | None = None
    reply_to: str | None = None


class StateEvent(BaseModel):
    type: str
    state_key: str
    content: dict[str, Any]
    sender: str
    origin_server_ts: int


class PowerLevels(BaseModel):
    users_default: int = 0
    events_default: int = 0
    state_default: int = 50
    ban: int = 50
    kick: int = 50
    redact: int = 50
    invite: int = 0
    users: dict[str, int] = Field(default_factory=dict)
    events: dict[str, int] = Field(default_factory=dict)


class RoomSummary(BaseModel):
    room_id: str
    display_name: str
    topic: str | None = None
    member_count: int
    unread_count: int
    is_encrypted: bool
    is_direct: bool


class RoomDetail(BaseModel):
    room_id: str
    display_name: str
    canonical_alias: str | None = None
    aliases: list[str] = Field(default_factory=list)
    topic: str | None = None
    avatar_url: str | None = None
    member_count: int
    is_encrypted: bool
    encryption_algorithm: str | None = None
    is_direct: bool
    creation_ts: int
    power_levels: PowerLevels


class Member(BaseModel):
    user_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    membership: str
    power_level: int


class UserProfile(BaseModel):
    user_id: str
    display_name: str | None = None
    avatar_url: str | None = None


class SearchResult(BaseModel):
    rank: float
    event: Message
    context_before: list[Message] = Field(default_factory=list)
    context_after: list[Message] = Field(default_factory=list)


class DMSummary(BaseModel):
    room_id: str
    user_id: str
    display_name: str | None = None
    unread_count: int


class SpaceChild(BaseModel):
    room_id: str
    display_name: str | None = None
    topic: str | None = None
    member_count: int
    is_space: bool


# ---------------------------------------------------------------------------
# Tool inputs
# ---------------------------------------------------------------------------

class SendMessageInput(BaseModel):
    room_id: str
    body: str
    format: str = "plain"  # "plain" | "markdown"
    reply_to_event_id: str | None = None


class SendReactionInput(BaseModel):
    room_id: str
    event_id: str
    reaction: str


class RedactEventInput(BaseModel):
    room_id: str
    event_id: str
    reason: str | None = None


class GetMessagesInput(BaseModel):
    room_id: str
    limit: int = Field(default=50, ge=1, le=500)
    from_token: str | None = None
    direction: str = "backward"  # "forward" | "backward"


class GetEventInput(BaseModel):
    room_id: str
    event_id: str


class SearchMessagesInput(BaseModel):
    query: str
    room_ids: list[str] | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetRoomInput(BaseModel):
    room_id: str


class CreateRoomInput(BaseModel):
    name: str | None = None
    alias: str | None = None
    topic: str | None = None
    is_direct: bool = False
    is_public: bool = False
    encrypted: bool = True
    invite: list[str] = Field(default_factory=list)
    preset: str | None = None  # "private_chat" | "public_chat" | "trusted_private_chat"


class JoinRoomInput(BaseModel):
    room_id_or_alias: str
    server_hint: str | None = None


class LeaveRoomInput(BaseModel):
    room_id: str


class SetRoomNameInput(BaseModel):
    room_id: str
    name: str


class SetRoomTopicInput(BaseModel):
    room_id: str
    topic: str


class GetRoomStateInput(BaseModel):
    room_id: str
    event_type: str | None = None


class SendStateEventInput(BaseModel):
    room_id: str
    event_type: str
    state_key: str = ""
    content: dict[str, Any]


class GetRoomMembersInput(BaseModel):
    room_id: str
    membership: str | None = "join"  # "join" | "invite" | "leave" | "ban" | None


class InviteUserInput(BaseModel):
    room_id: str
    user_id: str


class KickUserInput(BaseModel):
    room_id: str
    user_id: str
    reason: str | None = None


class BanUserInput(BaseModel):
    room_id: str
    user_id: str
    reason: str | None = None


class UnbanUserInput(BaseModel):
    room_id: str
    user_id: str


class SetPowerLevelInput(BaseModel):
    room_id: str
    user_id: str
    power_level: int = Field(ge=0, le=100)


class CreateDMInput(BaseModel):
    user_id: str


class GetUserProfileInput(BaseModel):
    user_id: str


class SetDisplayNameInput(BaseModel):
    display_name: str


class SendFileInput(BaseModel):
    room_id: str
    file_path: str
    filename: str | None = None
    mimetype: str | None = None
    caption: str | None = None


class DownloadMediaInput(BaseModel):
    mxc_uri: str
    dest_path: str


class ListSpaceChildrenInput(BaseModel):
    space_room_id: str


class AddRoomToSpaceInput(BaseModel):
    space_room_id: str
    child_room_id: str
    suggested: bool = False
