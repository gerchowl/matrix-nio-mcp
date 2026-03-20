# matrix-nio-mcp — Specification & Design Document

**Version:** 0.1.0-draft
**Status:** Pre-development
**Date:** 2026-03-20

---

## 1. Overview

`matrix-nio-mcp` is a Model Context Protocol (MCP) server that exposes the Matrix
Client-Server API to AI assistants. It is built on `matrix-nio`, a well-maintained,
async-first Python Matrix client library with native E2EE support.

The server allows an LLM (e.g. Claude) to read and write to Matrix rooms, manage
rooms and membership, and interact with a homeserver programmatically — all through
a clean, typed MCP tool interface.

### Goals

- Full Matrix Client-Server API coverage for AI-relevant operations
- Native E2EE: encrypted rooms are first-class, not an afterthought
- Single persistent session with proper device registration (not ephemeral per-call)
- Clean, typed tool interfaces — every tool has strict input/output schemas
- Production-ready: structured logging, graceful shutdown, retry logic
- Zero secrets in config files — credentials via environment variables

### Non-goals

- Voice/VoIP (calls, Jitsi integration)
- Server-side admin API (Synapse admin)
- Multi-account / multi-homeserver per server instance (use multiple instances)
- Media transcoding or processing

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    MCP Host (Claude)                 │
│                                                     │
│  tool_call("send_message", {...})                   │
└────────────────────┬────────────────────────────────┘
                     │  MCP stdio / SSE transport
┌────────────────────▼────────────────────────────────┐
│                matrix-nio-mcp server                │
│                                                     │
│  ┌──────────────┐   ┌──────────────────────────┐   │
│  │  MCP Layer   │   │    Session Manager        │   │
│  │  (tool reg,  │◄──│  (single AsyncClient,     │   │
│  │   schemas,   │   │   auto-reconnect,         │   │
│  │   dispatch)  │   │   E2EE key store)         │   │
│  └──────────────┘   └────────────┬─────────────┘   │
│                                  │                  │
└──────────────────────────────────┼──────────────────┘
                                   │  HTTPS + WSS
                          ┌────────▼──────────┐
                          │  Matrix Homeserver │
                          │  (Synapse/Dendrite)│
                          └───────────────────┘
```

### Component breakdown

| Component | Responsibility |
|---|---|
| `server.py` | Entry point. Registers all tools, starts MCP server (stdio or SSE). |
| `session.py` | Manages the `AsyncClient` lifecycle: login, sync loop, reconnect, shutdown. |
| `tools/` | One module per tool group (messages, rooms, members, profile, media). |
| `schemas.py` | Pydantic models for all tool inputs and outputs. |
| `config.py` | Config loading from env vars + optional TOML file. |
| `store/` | E2EE SQLite store path management (nio's `SqliteStore`). |
| `logging.py` | Structured logging via `structlog`. |

---

## 3. Configuration

All secrets via environment variables. Optional overrides via `config.toml`.

### Required env vars

| Variable | Description |
|---|---|
| `MATRIX_HOMESERVER` | Full URL e.g. `https://matrix.example.com` |
| `MATRIX_USER_ID` | Full user ID e.g. `@bot:example.com` |
| `MATRIX_ACCESS_TOKEN` | Access token (preferred over password) |

### Optional env vars

| Variable | Default | Description |
|---|---|---|
| `MATRIX_DEVICE_ID` | auto-generated | Stable device ID for E2EE continuity |
| `MATRIX_DEVICE_NAME` | `matrix-nio-mcp` | Display name for device |
| `MATRIX_STORE_PATH` | `~/.local/share/matrix-nio-mcp/store` | SQLite E2EE store location |
| `MATRIX_SYNC_TIMEOUT` | `30000` | Long-poll sync timeout (ms) |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `MCP_SSE_PORT` | `8000` | Port for SSE transport |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### config.toml (optional overrides, no secrets)

```toml
[matrix]
sync_timeout = 30000
device_name = "matrix-nio-mcp"
store_path = "~/.local/share/matrix-nio-mcp/store"

[mcp]
transport = "stdio"
sse_port = 8000

[logging]
level = "INFO"
format = "json"  # "json" or "pretty"
```

---

## 4. Session Management

The server maintains a **single, persistent `nio.AsyncClient`** for its lifetime.
This is critical for E2EE — ephemeral clients per tool call would require a full key
exchange on every request and cannot participate in encrypted rooms reliably.

### Startup sequence

1. Load config from env + optional TOML
2. Initialize `SqliteStore` at configured path
3. Create `AsyncClient` with store
4. Login (access token preferred; password fallback)
5. Run initial `sync()` to hydrate room state and download E2EE keys
6. Register to-device message handler for key requests
7. Start background sync loop (long-poll)
8. Register MCP tools
9. Start MCP server

### Sync loop

The sync loop runs as an `asyncio` background task. It:
- Long-polls the homeserver (`/sync?timeout=30000`)
- Processes to-device events (key requests, key share)
- Updates local room state
- Does NOT deliver every message to the LLM — messages are fetched on demand

### Reconnect strategy

Exponential backoff: 1s → 2s → 4s → ... → 60s cap. After 5 consecutive failures,
logs a critical error but keeps retrying indefinitely.

### Shutdown

On SIGTERM/SIGINT: stop sync loop, logout device (optional, configurable), close
the client, flush logs.

---

## 5. Tool Catalogue

### 5.1 Messaging

#### `send_message`
Send a text message to a room. Supports plain text and Markdown (rendered to
Matrix's `m.text` + `formatted_body`). Handles E2EE automatically.

```
Input:
  room_id: str          # !roomid:server or alias #room:server
  body: str             # Message content
  format: "plain" | "markdown"   # default: "plain"
  reply_to_event_id: str | None  # Thread reply

Output:
  event_id: str
  timestamp: int
```

#### `send_notice`
Same as `send_message` but sends `m.notice` (bot-style, typically rendered
differently by clients — useful to avoid notification pings).

#### `send_reaction`
React to an existing event with an emoji.

```
Input:
  room_id: str
  event_id: str         # Event to react to
  reaction: str         # Emoji or short string

Output:
  event_id: str
```

#### `redact_event`
Redact (delete) a message by event ID. Only works if the bot has sufficient
power level.

```
Input:
  room_id: str
  event_id: str
  reason: str | None

Output:
  redaction_event_id: str
```

#### `get_messages`
Fetch the message timeline for a room, paginated.

```
Input:
  room_id: str
  limit: int            # default: 50, max: 500
  from_token: str | None   # Pagination token (from previous response)
  direction: "forward" | "backward"   # default: "backward" (newest first)

Output:
  messages: List[Message]
    - event_id: str
    - sender: str
    - timestamp: int
    - type: str         # "text" | "notice" | "image" | "file" | "redacted" | ...
    - body: str
    - formatted_body: str | None
    - reply_to: str | None
  next_token: str | None
```

#### `get_event`
Fetch a single event by ID.

```
Input:
  room_id: str
  event_id: str

Output:
  event: Message
```

#### `search_messages`
Full-text search across rooms (uses Matrix `/search` API).

```
Input:
  query: str
  room_ids: List[str] | None   # Scope to specific rooms; None = all
  limit: int                   # default: 20

Output:
  results: List[SearchResult]
    - rank: float
    - event: Message
    - context_before: List[Message]
    - context_after: List[Message]
```

---

### 5.2 Room Management

#### `list_rooms`
List all rooms the bot account has joined.

```
Output:
  rooms: List[RoomSummary]
    - room_id: str
    - display_name: str
    - topic: str | None
    - member_count: int
    - unread_count: int
    - is_encrypted: bool
    - is_direct: bool
```

#### `get_room`
Get detailed metadata for a specific room.

```
Input:
  room_id: str

Output:
  room_id: str
  display_name: str
  canonical_alias: str | None
  aliases: List[str]
  topic: str | None
  avatar_url: str | None
  member_count: int
  is_encrypted: bool
  encryption_algorithm: str | None
  is_direct: bool
  creation_ts: int
  power_levels: PowerLevels
```

#### `create_room`
Create a new Matrix room.

```
Input:
  name: str | None
  alias: str | None         # Local part only, e.g. "my-room" → #my-room:server
  topic: str | None
  is_direct: bool           # default: false
  is_public: bool           # default: false
  encrypted: bool           # default: true
  invite: List[str]         # User IDs to invite on creation
  preset: "private_chat" | "public_chat" | "trusted_private_chat" | None

Output:
  room_id: str
```

#### `join_room`
Join a room by ID or alias.

```
Input:
  room_id_or_alias: str
  server_hint: str | None   # Homeserver to route join through

Output:
  room_id: str
```

#### `leave_room`

```
Input:
  room_id: str

Output:
  success: bool
```

#### `set_room_name`

```
Input:
  room_id: str
  name: str

Output:
  event_id: str
```

#### `set_room_topic`

```
Input:
  room_id: str
  topic: str

Output:
  event_id: str
```

#### `get_room_state`
Fetch all current state events for a room (power levels, join rules, members, etc.).

```
Input:
  room_id: str
  event_type: str | None    # Filter by type, e.g. "m.room.power_levels"

Output:
  state_events: List[StateEvent]
    - type: str
    - state_key: str
    - content: dict
    - sender: str
    - origin_server_ts: int
```

#### `send_state_event`
Send an arbitrary state event (for advanced room config).

```
Input:
  room_id: str
  event_type: str
  state_key: str            # default: ""
  content: dict

Output:
  event_id: str
```

---

### 5.3 Membership Management

#### `get_room_members`

```
Input:
  room_id: str
  membership: "join" | "invite" | "leave" | "ban" | None   # Filter; default: "join"

Output:
  members: List[Member]
    - user_id: str
    - display_name: str | None
    - avatar_url: str | None
    - membership: str
    - power_level: int
```

#### `invite_user`

```
Input:
  room_id: str
  user_id: str

Output:
  success: bool
```

#### `kick_user`

```
Input:
  room_id: str
  user_id: str
  reason: str | None

Output:
  success: bool
```

#### `ban_user`

```
Input:
  room_id: str
  user_id: str
  reason: str | None

Output:
  success: bool
```

#### `unban_user`

```
Input:
  room_id: str
  user_id: str

Output:
  success: bool
```

#### `set_power_level`
Set a user's power level in a room.

```
Input:
  room_id: str
  user_id: str
  power_level: int         # 0–100; 100 = admin

Output:
  event_id: str
```

---

### 5.4 Direct Messages

#### `create_dm`
Create or retrieve an existing DM room with a user.

```
Input:
  user_id: str

Output:
  room_id: str
  created: bool
```

#### `list_dms`
List all DM rooms.

```
Output:
  dms: List[DMSummary]
    - room_id: str
    - user_id: str
    - display_name: str | None
    - unread_count: int
```

---

### 5.5 Profile

#### `get_user_profile`

```
Input:
  user_id: str

Output:
  user_id: str
  display_name: str | None
  avatar_url: str | None
```

#### `set_display_name`

```
Input:
  display_name: str

Output:
  success: bool
```

#### `whoami`
Return the bot's own user ID and device ID.

```
Output:
  user_id: str
  device_id: str
  homeserver: str
```

---

### 5.6 Media

#### `send_file`
Upload and send a file (image, document, etc.) to a room.

```
Input:
  room_id: str
  file_path: str           # Local path to file
  filename: str | None     # Override filename; default: basename of path
  mimetype: str | None     # Auto-detected if omitted
  caption: str | None      # Optional accompanying text

Output:
  event_id: str
  mxc_uri: str
```

#### `download_media`
Download a media file from a Matrix MXC URI to a local path.

```
Input:
  mxc_uri: str
  dest_path: str

Output:
  dest_path: str
  filename: str
  size_bytes: int
```

---

### 5.7 Spaces (Matrix Spaces)

#### `list_space_children`
List rooms within a Matrix Space.

```
Input:
  space_room_id: str

Output:
  children: List[SpaceChild]
    - room_id: str
    - display_name: str | None
    - topic: str | None
    - member_count: int
    - is_space: bool
```

#### `add_room_to_space`

```
Input:
  space_room_id: str
  child_room_id: str
  suggested: bool          # default: false

Output:
  event_id: str
```

---

## 6. E2EE Design

E2EE is a first-class feature, not optional. The server:

1. **Uses `SqliteStore`** — persists Olm sessions, Megolm sessions, and device keys
   across restarts. The store path must be stable for a given device ID.

2. **Handles key requests** — processes `m.room_key_request` to-device events in the
   sync loop, re-sharing keys to verified devices on request.

3. **Trust policy (configurable)**:
   - `TOFU` (Trust On First Use) — default. Trust any device seen for the first time.
   - `verified_only` — only decrypt/encrypt for verified devices. Others silently dropped.
   - `blacklist` — explicit per-device blacklist.

4. **Encrypted room detection** — `send_message` and related tools automatically
   detect if the room is encrypted and use `encrypt()` before sending.

5. **Key backup (future)** — Sesame / SSSS key backup support is planned but out of
   scope for v1.

---

## 7. Error Handling

All tools return structured errors using MCP's `isError` mechanism, not Python
exceptions bubbling up.

| Error class | Description |
|---|---|
| `MatrixAuthError` | Token expired, invalid credentials |
| `MatrixPermissionError` | Insufficient power level for the operation |
| `MatrixRoomNotFound` | Room ID/alias does not resolve |
| `MatrixUserNotFound` | User ID does not exist on homeserver |
| `MatrixEncryptionError` | E2EE key missing, device not trusted, etc. |
| `MatrixRateLimitError` | 429 from homeserver; includes `retry_after_ms` |
| `MatrixNetworkError` | Connection failure, timeout |
| `ValidationError` | Invalid tool input (Pydantic) |

Rate limit errors automatically retry with backoff before surfacing to the LLM.

---

## 8. Testing Strategy

### Unit tests
- All tool input/output schemas validated with Pydantic
- Session manager state transitions (login, reconnect, shutdown)
- Error mapping (homeserver error codes → tool errors)

### Integration tests
Use a local [Synapse](https://github.com/element-hq/synapse) instance via Docker:
- Create rooms, send messages, verify retrieval
- E2EE round-trip: encrypt → send → fetch → decrypt
- Membership operations: invite, kick, ban

### Fixture homeserver
`docker-compose.yml` included in repo for a local Synapse + test user bootstrap.

---

## 9. Project Layout

```
matrix-nio-mcp/
├── flake.nix
├── .envrc
├── justfile                  # just fmt, just test, just run, just lint
├── config.toml.example
├── SPEC.md
│
├── src/
│   └── matrix_nio_mcp/
│       ├── __init__.py
│       ├── server.py         # Entry point, MCP server setup
│       ├── session.py        # AsyncClient lifecycle
│       ├── config.py         # Config loading
│       ├── schemas.py        # Pydantic I/O models
│       ├── logging.py        # structlog setup
│       ├── errors.py         # Error classes + mapping
│       │
│       └── tools/
│           ├── __init__.py
│           ├── messages.py
│           ├── rooms.py
│           ├── members.py
│           ├── profile.py
│           ├── media.py
│           └── spaces.py
│
├── tests/
│   ├── unit/
│   └── integration/
│       └── docker-compose.yml
│
└── pyproject.toml
```

---

## 10. Dependency Summary

| Package | Purpose |
|---|---|
| `matrix-nio[e2e]` | Matrix client + E2EE (Olm/Megolm) |
| `mcp[cli]` | MCP server framework (Anthropic) |
| `pydantic` | Input/output schema validation |
| `structlog` | Structured async-safe logging |
| `aiofiles` | Async file I/O for media upload |
| `tomli` | TOML config parsing (Python < 3.11 compat) |
| `python-dotenv` | `.env` file support in development |
| `pytest` + `pytest-asyncio` | Testing |
| `ruff` | Linting + formatting |
| `mypy` | Static type checking |

System deps (via Nix):
| Package | Purpose |
|---|---|
| `libolm` | C library backing E2EE in matrix-nio |
| `sqlite` | E2EE key store backend |

---

## 11. Open Questions / Future Work

- **Key verification UX** — how should an LLM handle a device verification request
  mid-session? (Emoji SAS is interactive by nature.) Likely: auto-TOFU for v1,
  structured verification tool for v2.
- **Webhook / push mode** — instead of on-demand `get_messages`, push new messages
  to the LLM via MCP resource subscriptions or sampling. Requires MCP sampling spec
  stabilisation.
- **Multi-account** — run multiple server instances behind a reverse proxy with
  per-account config, or add multi-account support natively.
- **Synapse admin tools** — separate MCP server for admin API (room purge, user
  deactivation, media quarantine).
- **Read receipts & typing notifications** — low priority but completeness item.
