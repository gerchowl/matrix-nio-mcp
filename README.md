# matrix-nio-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes a Matrix homeserver to LLM agents via [matrix-nio](https://github.com/poljar/matrix-nio).

Supports 29 tools covering messages, rooms, members, profiles, media, and spaces — with full E2EE support.

## Quick Start

### 1. Create a Matrix bot account

Register a dedicated account on your homeserver. Retrieve an access token via:

```bash
curl -XPOST 'https://matrix.example.com/_matrix/client/v3/login' \
  -H 'Content-Type: application/json' \
  -d '{"type":"m.login.password","user":"@bot:example.com","password":"<password>"}'
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run

**With uv (recommended):**
```bash
uv sync --all-groups
just run
```

**With pip:**
```bash
pip install -e .
python -m matrix_nio_mcp.server
```

**With container (podman):**
```bash
just build
podman run --rm -it \
  --env-file .env \
  -v matrix-nio-mcp-store:/data/store \
  matrix-nio-mcp
```

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "matrix": {
      "command": "python",
      "args": ["-m", "matrix_nio_mcp.server"],
      "env": {
        "MATRIX_HOMESERVER": "https://matrix.example.com",
        "MATRIX_USER_ID": "@bot:example.com",
        "MATRIX_ACCESS_TOKEN": "syt_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

Or using the container:

```json
{
  "mcpServers": {
    "matrix": {
      "command": "podman",
      "args": [
        "run", "--rm", "-i",
        "-e", "MATRIX_HOMESERVER=https://matrix.example.com",
        "-e", "MATRIX_USER_ID=@bot:example.com",
        "-e", "MATRIX_ACCESS_TOKEN=syt_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "-v", "matrix-nio-mcp-store:/data/store",
        "matrix-nio-mcp"
      ]
    }
  }
}
```

## SSE Transport

For persistent deployments (e.g., connecting multiple clients):

```bash
MCP_TRANSPORT=sse MCP_SSE_PORT=8000 python -m matrix_nio_mcp.server
```

The server exposes:
- `GET /sse` — SSE connection endpoint for MCP clients
- `POST /messages/` — MCP message endpoint
- `GET /health` — Health check: `{"status": "ok", "user_id": "@bot:example.com"}`

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MATRIX_HOMESERVER` | ✓ | — | Homeserver URL |
| `MATRIX_USER_ID` | ✓ | — | Bot Matrix ID (`@bot:example.com`) |
| `MATRIX_ACCESS_TOKEN` | ✓ | — | Bot access token |
| `MATRIX_DEVICE_ID` | | auto | Stable device ID for E2EE continuity |
| `MATRIX_DEVICE_NAME` | | `matrix-nio-mcp` | Device display name |
| `MATRIX_STORE_PATH` | | `~/.local/share/matrix-nio-mcp/store` | E2EE key store path |
| `MATRIX_SYNC_TIMEOUT` | | `30000` | Sync long-poll timeout (ms) |
| `MATRIX_TRUST_POLICY` | | `TOFU` | Key trust policy: `TOFU` or `VERIFIED` |
| `MCP_TRANSPORT` | | `stdio` | `stdio` or `sse` |
| `MCP_SSE_PORT` | | `8000` | SSE server port |
| `LOG_LEVEL` | | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | | `json` | `json` or `pretty` |

## Available Tools

### Messaging
| Tool | Description |
|---|---|
| `send_message` | Send a text message (plain or Markdown) |
| `send_notice` | Send a bot notice (m.notice) |
| `send_reaction` | React to a message with an emoji |
| `redact_event` | Delete (redact) a message |
| `get_messages` | Fetch message timeline with pagination |
| `get_event` | Fetch a single event by ID |
| `search_messages` | Full-text search across rooms |

### Rooms
| Tool | Description |
|---|---|
| `list_rooms` | List all joined rooms |
| `get_room` | Get room metadata and power levels |
| `create_room` | Create a room (with optional encryption) |
| `join_room` | Join by ID or alias |
| `leave_room` | Leave a room |
| `set_room_name` | Update room name |
| `set_room_topic` | Update room topic |
| `get_room_state` | Fetch state events |
| `send_state_event` | Send arbitrary state event |

### Members
| Tool | Description |
|---|---|
| `get_room_members` | List members (filterable by membership) |
| `invite_user` | Invite a user |
| `kick_user` | Kick with optional reason |
| `ban_user` | Ban with optional reason |
| `unban_user` | Reverse a ban |
| `set_power_level` | Set user power level (0–100) |

### Profile & DMs
| Tool | Description |
|---|---|
| `get_user_profile` | Get display name and avatar |
| `set_display_name` | Update bot display name |
| `whoami` | Return bot's user ID and device ID |
| `create_dm` | Create or retrieve a DM room |
| `list_dms` | List all DM rooms |

### Media
| Tool | Description |
|---|---|
| `send_file` | Upload and send a file |
| `download_media` | Download an MXC URI to a local path |

### Spaces
| Tool | Description |
|---|---|
| `list_space_children` | List rooms in a Matrix Space |
| `add_room_to_space` | Add a room to a Space |

## E2EE Notes

- E2EE is enabled by default. Set `MATRIX_STORE_PATH` to a persistent volume to preserve key material across restarts.
- Set a stable `MATRIX_DEVICE_ID` to avoid re-establishing sessions after restarts.
- Trust policy `TOFU` (default) automatically re-shares Megolm session keys to devices that request them. Use `VERIFIED` for stricter cross-signing environments.
- Key material is stored in a SQLite database at `MATRIX_STORE_PATH`.

## Development

```bash
just install       # create .venv and install all deps
just test-unit     # run unit tests
just lint          # ruff check
just fmt           # ruff format
just typecheck     # mypy strict
just dev           # SSE server with pretty logs
just build         # build container image
just synapse-up    # start local Synapse for integration tests
just test-integration
just synapse-down
```

## License

MIT
