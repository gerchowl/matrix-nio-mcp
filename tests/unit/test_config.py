"""Unit tests for config loading."""

import os
import pytest

from matrix_nio_mcp.config import load


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.com")
    monkeypatch.setenv("MATRIX_USER_ID", "@bot:example.com")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")

    cfg = load()

    assert cfg.matrix.homeserver == "https://matrix.example.com"
    assert cfg.matrix.user_id == "@bot:example.com"
    assert cfg.matrix.access_token == "syt_test_token"
    assert cfg.matrix.sync_timeout == 30_000
    assert cfg.matrix.device_name == "matrix-nio-mcp"


def test_missing_homeserver_raises(monkeypatch):
    monkeypatch.delenv("MATRIX_HOMESERVER", raising=False)
    monkeypatch.setenv("MATRIX_USER_ID", "@bot:example.com")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "token")

    with pytest.raises(ValueError, match="MATRIX_HOMESERVER"):
        load()


def test_missing_token_raises(monkeypatch):
    monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.com")
    monkeypatch.setenv("MATRIX_USER_ID", "@bot:example.com")
    monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MATRIX_ACCESS_TOKEN"):
        load()


def test_optional_env_overrides(monkeypatch):
    monkeypatch.setenv("MATRIX_HOMESERVER", "https://matrix.example.com")
    monkeypatch.setenv("MATRIX_USER_ID", "@bot:example.com")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "token")
    monkeypatch.setenv("MATRIX_SYNC_TIMEOUT", "10000")
    monkeypatch.setenv("MCP_TRANSPORT", "sse")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    cfg = load()

    assert cfg.matrix.sync_timeout == 10_000
    assert cfg.mcp.transport == "sse"
    assert cfg.log.level == "DEBUG"
