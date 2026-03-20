"""Integration test fixtures — requires running Synapse (see docker-compose.yml)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYNAPSE_URL = os.environ.get("SYNAPSE_URL", "http://localhost:8448")
SHARED_SECRET = os.environ.get("SYNAPSE_SHARED_SECRET", "integration-test-secret")
_user_counter = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_synapse(timeout: int = 60) -> None:
    """Block until Synapse is healthy or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{SYNAPSE_URL}/_matrix/client/versions", timeout=3)
            if r.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Synapse at {SYNAPSE_URL} did not become healthy within {timeout}s")


def _register_user(username: str, password: str = "password123") -> str:
    """Register user via shared-secret registration. Returns access token."""
    import hashlib
    import hmac

    nonce_r = httpx.get(f"{SYNAPSE_URL}/_synapse/admin/v1/register", timeout=10)
    nonce = nonce_r.json()["nonce"]

    mac = hmac.new(
        SHARED_SECRET.encode(),
        digestmod=hashlib.sha1,
    )
    mac.update(nonce.encode())
    mac.update(b"\x00")
    mac.update(username.encode())
    mac.update(b"\x00")
    mac.update(password.encode())
    mac.update(b"\x00")
    mac.update(b"notadmin")
    digest = mac.hexdigest()

    resp = httpx.post(
        f"{SYNAPSE_URL}/_synapse/admin/v1/register",
        json={
            "nonce": nonce,
            "username": username,
            "password": password,
            "admin": False,
            "mac": digest,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Session-scoped: one Synapse check per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def synapse_health() -> None:
    """Fail fast if Synapse is not running."""
    _wait_for_synapse()


# ---------------------------------------------------------------------------
# Function-scoped: fresh user + Session per test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def matrix_session() -> AsyncGenerator:
    """Yield a started Session for a freshly-registered test user."""
    global _user_counter
    _user_counter += 1
    username = f"testbot{_user_counter}"

    token = _register_user(username)

    from matrix_nio_mcp.config import Config, LogConfig, MatrixConfig, McpConfig
    from matrix_nio_mcp.session import Session
    import tempfile, pathlib

    store_dir = pathlib.Path(tempfile.mkdtemp())

    cfg = Config(
        matrix=MatrixConfig(
            homeserver=SYNAPSE_URL,
            user_id=f"@{username}:localhost",
            access_token=token,
            store_path=store_dir,
        ),
        mcp=McpConfig(),
        log=LogConfig(),
    )

    session = Session(cfg)
    await session.start()

    yield session

    await session.stop()


@pytest_asyncio.fixture
async def second_user() -> AsyncGenerator:
    """A second registered user's access token (for invite/kick tests)."""
    global _user_counter
    _user_counter += 1
    username = f"testuser{_user_counter}"
    token = _register_user(username)
    yield f"@{username}:localhost", token
