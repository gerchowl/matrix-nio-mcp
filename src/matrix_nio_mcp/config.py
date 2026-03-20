"""Config loading: env vars + optional config.toml."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class MatrixConfig:
    homeserver: str
    user_id: str
    access_token: str
    device_id: str | None = None
    device_name: str = "matrix-nio-mcp"
    store_path: Path = field(
        default_factory=lambda: Path.home() / ".local/share/matrix-nio-mcp/store"
    )
    sync_timeout: int = 30_000
    trust_policy: str = "TOFU"  # "TOFU" | "verified_only"


@dataclass
class McpConfig:
    transport: str = "stdio"  # "stdio" | "sse"
    sse_port: int = 8000


@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "json"  # "json" | "pretty"


@dataclass
class Config:
    matrix: MatrixConfig
    mcp: McpConfig
    log: LogConfig


def load(config_path: Path | None = None) -> Config:
    """Load config from env vars, with optional TOML overrides."""
    toml: dict = {}
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            toml = tomllib.load(f)
    elif (p := Path("config.toml")).exists():
        with open(p, "rb") as f:
            toml = tomllib.load(f)

    m = toml.get("matrix", {})
    mcp = toml.get("mcp", {})
    log = toml.get("logging", {})

    homeserver = os.environ.get("MATRIX_HOMESERVER") or m.get("homeserver", "")
    user_id = os.environ.get("MATRIX_USER_ID") or m.get("user_id", "")
    access_token = os.environ.get("MATRIX_ACCESS_TOKEN") or m.get("access_token", "")

    if not homeserver:
        raise ValueError("MATRIX_HOMESERVER is required")
    if not user_id:
        raise ValueError("MATRIX_USER_ID is required")
    if not access_token:
        raise ValueError("MATRIX_ACCESS_TOKEN is required")

    raw_store = (
        os.environ.get("MATRIX_STORE_PATH")
        or m.get("store_path", "~/.local/share/matrix-nio-mcp/store")
    )
    store_path = Path(raw_store).expanduser()

    return Config(
        matrix=MatrixConfig(
            homeserver=homeserver,
            user_id=user_id,
            access_token=access_token,
            device_id=os.environ.get("MATRIX_DEVICE_ID") or m.get("device_id"),
            device_name=(
                os.environ.get("MATRIX_DEVICE_NAME")
                or m.get("device_name", "matrix-nio-mcp")
            ),
            store_path=store_path,
            sync_timeout=int(
                os.environ.get("MATRIX_SYNC_TIMEOUT") or m.get("sync_timeout", 30_000)
            ),
            trust_policy=m.get("trust_policy", "TOFU"),
        ),
        mcp=McpConfig(
            transport=os.environ.get("MCP_TRANSPORT") or mcp.get("transport", "stdio"),
            sse_port=int(os.environ.get("MCP_SSE_PORT") or mcp.get("sse_port", 8000)),
        ),
        log=LogConfig(
            level=os.environ.get("LOG_LEVEL") or log.get("level", "INFO"),
            format=log.get("format", "json"),
        ),
    )
