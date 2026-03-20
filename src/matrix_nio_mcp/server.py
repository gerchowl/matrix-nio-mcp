"""MCP server entry point. Registers all tools and starts the server."""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from . import log as _log
from .config import load as load_config
from .errors import MatrixError
from .schemas import (
    AddRoomToSpaceInput,
    BanUserInput,
    CreateDMInput,
    CreateRoomInput,
    DownloadMediaInput,
    GetEventInput,
    GetMessagesInput,
    GetRoomInput,
    GetRoomMembersInput,
    GetRoomStateInput,
    GetUserProfileInput,
    InviteUserInput,
    JoinRoomInput,
    KickUserInput,
    LeaveRoomInput,
    ListSpaceChildrenInput,
    RedactEventInput,
    SearchMessagesInput,
    SendFileInput,
    SendMessageInput,
    SendReactionInput,
    SendStateEventInput,
    SetDisplayNameInput,
    SetPowerLevelInput,
    SetRoomNameInput,
    SetRoomTopicInput,
    UnbanUserInput,
)
from .session import Session
from .tools import members, media, messages, profile, rooms, spaces

load_dotenv()

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

_TOOLS: list[Tool] = [
    # Messaging
    Tool(name="send_message", description="Send a text message to a Matrix room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "body": {"type": "string"},
            "format": {"type": "string", "enum": ["plain", "markdown"], "default": "plain"},
            "reply_to_event_id": {"type": "string"},
        },
        "required": ["room_id", "body"],
    }),
    Tool(name="send_notice", description="Send a bot notice (m.notice) to a Matrix room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "body": {"type": "string"},
            "format": {"type": "string", "enum": ["plain", "markdown"], "default": "plain"},
        },
        "required": ["room_id", "body"],
    }),
    Tool(name="send_reaction", description="React to a message with an emoji", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "event_id": {"type": "string"},
            "reaction": {"type": "string"},
        },
        "required": ["room_id", "event_id", "reaction"],
    }),
    Tool(name="redact_event", description="Delete (redact) a message", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "event_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["room_id", "event_id"],
    }),
    Tool(name="get_messages", description="Fetch message timeline for a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
            "from_token": {"type": "string"},
            "direction": {"type": "string", "enum": ["forward", "backward"], "default": "backward"},
        },
        "required": ["room_id"],
    }),
    Tool(name="get_event", description="Fetch a single event by ID", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "event_id": {"type": "string"},
        },
        "required": ["room_id", "event_id"],
    }),
    Tool(name="search_messages", description="Full-text search across rooms", inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "room_ids": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
        },
        "required": ["query"],
    }),
    # Rooms
    Tool(name="list_rooms", description="List all rooms the bot has joined", inputSchema={
        "type": "object", "properties": {},
    }),
    Tool(name="get_room", description="Get detailed metadata for a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}},
        "required": ["room_id"],
    }),
    Tool(name="create_room", description="Create a new Matrix room", inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "alias": {"type": "string"},
            "topic": {"type": "string"},
            "is_direct": {"type": "boolean", "default": False},
            "is_public": {"type": "boolean", "default": False},
            "encrypted": {"type": "boolean", "default": True},
            "invite": {"type": "array", "items": {"type": "string"}},
            "preset": {"type": "string", "enum": ["private_chat", "public_chat", "trusted_private_chat"]},
        },
    }),
    Tool(name="join_room", description="Join a room by ID or alias", inputSchema={
        "type": "object",
        "properties": {
            "room_id_or_alias": {"type": "string"},
            "server_hint": {"type": "string"},
        },
        "required": ["room_id_or_alias"],
    }),
    Tool(name="leave_room", description="Leave a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}},
        "required": ["room_id"],
    }),
    Tool(name="set_room_name", description="Set the name of a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}, "name": {"type": "string"}},
        "required": ["room_id", "name"],
    }),
    Tool(name="set_room_topic", description="Set the topic of a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}, "topic": {"type": "string"}},
        "required": ["room_id", "topic"],
    }),
    Tool(name="get_room_state", description="Fetch state events for a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "event_type": {"type": "string"},
        },
        "required": ["room_id"],
    }),
    Tool(name="send_state_event", description="Send an arbitrary state event", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "event_type": {"type": "string"},
            "state_key": {"type": "string", "default": ""},
            "content": {"type": "object"},
        },
        "required": ["room_id", "event_type", "content"],
    }),
    # Members
    Tool(name="get_room_members", description="List members of a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "membership": {"type": "string", "enum": ["join", "invite", "leave", "ban"]},
        },
        "required": ["room_id"],
    }),
    Tool(name="invite_user", description="Invite a user to a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}, "user_id": {"type": "string"}},
        "required": ["room_id", "user_id"],
    }),
    Tool(name="kick_user", description="Kick a user from a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "user_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["room_id", "user_id"],
    }),
    Tool(name="ban_user", description="Ban a user from a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "user_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["room_id", "user_id"],
    }),
    Tool(name="unban_user", description="Unban a user from a room", inputSchema={
        "type": "object",
        "properties": {"room_id": {"type": "string"}, "user_id": {"type": "string"}},
        "required": ["room_id", "user_id"],
    }),
    Tool(name="set_power_level", description="Set a user's power level in a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "user_id": {"type": "string"},
            "power_level": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["room_id", "user_id", "power_level"],
    }),
    # Profile / DMs
    Tool(name="get_user_profile", description="Get a user's display name and avatar", inputSchema={
        "type": "object",
        "properties": {"user_id": {"type": "string"}},
        "required": ["user_id"],
    }),
    Tool(name="set_display_name", description="Set the bot's display name", inputSchema={
        "type": "object",
        "properties": {"display_name": {"type": "string"}},
        "required": ["display_name"],
    }),
    Tool(name="whoami", description="Return the bot's user ID and device ID", inputSchema={
        "type": "object", "properties": {},
    }),
    Tool(name="create_dm", description="Create or get an existing DM room with a user", inputSchema={
        "type": "object",
        "properties": {"user_id": {"type": "string"}},
        "required": ["user_id"],
    }),
    Tool(name="list_dms", description="List all DM rooms", inputSchema={
        "type": "object", "properties": {},
    }),
    # Media
    Tool(name="send_file", description="Upload and send a file to a room", inputSchema={
        "type": "object",
        "properties": {
            "room_id": {"type": "string"},
            "file_path": {"type": "string"},
            "filename": {"type": "string"},
            "mimetype": {"type": "string"},
            "caption": {"type": "string"},
        },
        "required": ["room_id", "file_path"],
    }),
    Tool(name="download_media", description="Download a Matrix MXC media file to a local path", inputSchema={
        "type": "object",
        "properties": {
            "mxc_uri": {"type": "string"},
            "dest_path": {"type": "string"},
        },
        "required": ["mxc_uri", "dest_path"],
    }),
    # Spaces
    Tool(name="list_space_children", description="List rooms within a Matrix Space", inputSchema={
        "type": "object",
        "properties": {"space_room_id": {"type": "string"}},
        "required": ["space_room_id"],
    }),
    Tool(name="add_room_to_space", description="Add a room to a Matrix Space", inputSchema={
        "type": "object",
        "properties": {
            "space_room_id": {"type": "string"},
            "child_room_id": {"type": "string"},
            "suggested": {"type": "boolean", "default": False},
        },
        "required": ["space_room_id", "child_room_id"],
    }),
]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def _dispatch(session: Session, name: str, args: dict[str, Any]) -> Any:
    match name:
        # --- Messaging ---
        case "send_message":
            return await messages.send_message(session, SendMessageInput(**args))
        case "send_notice":
            return await messages.send_notice(session, SendMessageInput(**args))
        case "send_reaction":
            return await messages.send_reaction(session, SendReactionInput(**args))
        case "redact_event":
            return await messages.redact_event(session, RedactEventInput(**args))
        case "get_messages":
            return await messages.get_messages(session, GetMessagesInput(**args))
        case "get_event":
            return await messages.get_event(session, GetEventInput(**args))
        case "search_messages":
            return await messages.search_messages(session, SearchMessagesInput(**args))
        # --- Rooms ---
        case "list_rooms":
            return await rooms.list_rooms(session)
        case "get_room":
            return await rooms.get_room(session, GetRoomInput(**args))
        case "create_room":
            return await rooms.create_room(session, CreateRoomInput(**args))
        case "join_room":
            return await rooms.join_room(session, JoinRoomInput(**args))
        case "leave_room":
            return await rooms.leave_room(session, LeaveRoomInput(**args))
        case "set_room_name":
            return await rooms.set_room_name(session, SetRoomNameInput(**args))
        case "set_room_topic":
            return await rooms.set_room_topic(session, SetRoomTopicInput(**args))
        case "get_room_state":
            return await rooms.get_room_state(session, GetRoomStateInput(**args))
        case "send_state_event":
            return await rooms.send_state_event(session, SendStateEventInput(**args))
        case "list_space_children":
            return await spaces.list_space_children(session, ListSpaceChildrenInput(**args))
        case "add_room_to_space":
            return await spaces.add_room_to_space(session, AddRoomToSpaceInput(**args))
        # --- Members ---
        case "get_room_members":
            return await members.get_room_members(session, GetRoomMembersInput(**args))
        case "invite_user":
            return await members.invite_user(session, InviteUserInput(**args))
        case "kick_user":
            return await members.kick_user(session, KickUserInput(**args))
        case "ban_user":
            return await members.ban_user(session, BanUserInput(**args))
        case "unban_user":
            return await members.unban_user(session, UnbanUserInput(**args))
        case "set_power_level":
            return await members.set_power_level(session, SetPowerLevelInput(**args))
        # --- Profile / DMs ---
        case "get_user_profile":
            return await profile.get_user_profile(session, GetUserProfileInput(**args))
        case "set_display_name":
            return await profile.set_display_name(session, SetDisplayNameInput(**args))
        case "whoami":
            return await profile.whoami(session)
        case "create_dm":
            return await profile.create_dm(session, CreateDMInput(**args))
        case "list_dms":
            return await profile.list_dms(session)
        # --- Media ---
        case "send_file":
            return await media.send_file(session, SendFileInput(**args))
        case "download_media":
            return await media.download_media(session, DownloadMediaInput(**args))
        case _:
            raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

async def _run() -> None:
    cfg = load_config()
    _log.configure(level=cfg.log.level, fmt=cfg.log.format)
    logger = _log.get(__name__)

    session = Session(cfg)
    await session.start()

    server = Server("matrix-nio-mcp")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return _TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        import time
        args = arguments or {}
        t0 = time.monotonic()
        logger.debug("tool_call_start", tool=name)
        try:
            result = await _dispatch(session, name, args)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info("tool_call_ok", tool=name, elapsed_ms=elapsed_ms)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        except MatrixError as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("tool_call_matrix_error", tool=name, error=exc.code, elapsed_ms=elapsed_ms)
            return [TextContent(type="text", text=json.dumps(exc.to_dict(), ensure_ascii=False))]
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("tool_call_error", tool=name, error=str(exc), elapsed_ms=elapsed_ms)
            return [TextContent(type="text", text=json.dumps({"error": "internal_error", "message": str(exc)}))]

    # Graceful shutdown
    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        logger.info("shutdown_signal")
        asyncio.create_task(session.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    logger.info("server_starting", transport=cfg.mcp.transport)

    if cfg.mcp.transport == "sse":
        from contextlib import asynccontextmanager

        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Mount, Route
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())

        async def health(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "user_id": cfg.matrix.user_id})

        @asynccontextmanager
        async def lifespan(app: Starlette):  # type: ignore[type-arg]
            yield
            await session.stop()

        app = Starlette(
            lifespan=lifespan,
            routes=[
                Route("/health", endpoint=health),
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        config = uvicorn.Config(app, host="0.0.0.0", port=cfg.mcp.sse_port, log_level="error")
        srv = uvicorn.Server(config)
        await srv.serve()
    else:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        await session.stop()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
