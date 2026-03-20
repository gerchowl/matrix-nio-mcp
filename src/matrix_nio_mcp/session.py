"""Manages a single persistent nio.AsyncClient for the server lifetime."""

from __future__ import annotations

import asyncio
from pathlib import Path

import nio  # type: ignore[import-untyped]

from . import log as _log
from .config import Config
from .errors import MatrixAuthError, MatrixNetworkError, raise_for_nio_response

logger = _log.get(__name__)

_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 60.0
_CRITICAL_FAILURES = 5


class Session:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._client: nio.AsyncClient | None = None
        self._sync_task: asyncio.Task | None = None
        self._consecutive_failures = 0

    @property
    def client(self) -> nio.AsyncClient:
        if self._client is None:
            raise RuntimeError("Session not started")
        return self._client

    async def start(self) -> None:
        cfg = self._cfg.matrix
        store_path = cfg.store_path
        store_path.mkdir(parents=True, exist_ok=True)

        client_config = nio.AsyncClientConfig(
            store_sync_tokens=True,
            encryption_enabled=True,
        )

        self._client = nio.AsyncClient(
            homeserver=cfg.homeserver,
            user=cfg.user_id,
            device_id=cfg.device_id,
            store_path=str(store_path),
            config=client_config,
        )

        logger.info("logging_in", user=cfg.user_id, homeserver=cfg.homeserver)
        resp = await self._client.login(
            token=cfg.access_token,
            device_name=cfg.device_name,
        )
        if isinstance(resp, nio.LoginError):
            raise MatrixAuthError(f"Login failed: {resp.message}")

        logger.info("login_ok", device_id=self._client.device_id)

        # Initial sync to hydrate room state and E2EE keys
        sync_resp = await self._client.sync(timeout=10_000, full_state=True)
        if isinstance(sync_resp, nio.SyncError):
            raise MatrixNetworkError(f"Initial sync failed: {sync_resp.message}")

        self._client.add_to_device_callback(self._handle_to_device, nio.KeyVerificationEvent)
        self._client.add_to_device_callback(self._handle_to_device, nio.RoomKeyRequest)
        self._sync_task = asyncio.create_task(self._sync_loop(), name="matrix-sync")
        logger.info("session_started")

    async def stop(self) -> None:
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.close()
            self._client = None

        logger.info("session_stopped")

    async def _sync_loop(self) -> None:
        client = self._client
        assert client is not None

        while True:
            try:
                resp = await client.sync(
                    timeout=self._cfg.matrix.sync_timeout,
                    full_state=False,
                )
                if isinstance(resp, nio.SyncError):
                    raise MatrixNetworkError(resp.message)

                self._consecutive_failures = 0

            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._consecutive_failures += 1
                delay = min(
                    _BACKOFF_BASE * (2 ** (self._consecutive_failures - 1)),
                    _BACKOFF_MAX,
                )
                if self._consecutive_failures >= _CRITICAL_FAILURES:
                    logger.critical(
                        "sync_critical_failure",
                        failures=self._consecutive_failures,
                        error=str(exc),
                    )
                else:
                    logger.warning(
                        "sync_error_backoff",
                        failures=self._consecutive_failures,
                        delay=delay,
                        error=str(exc),
                    )
                await asyncio.sleep(delay)

    async def _handle_to_device(self, room: object, event: nio.KeyVerificationEvent) -> None:
        logger.debug("to_device_event", type=type(event).__name__)

        # Re-share room keys on key requests (TOFU policy)
        if isinstance(event, nio.RoomKeyRequest):
            client = self._client
            if client is None:
                return
            action = getattr(event, "action", None)
            if action != "request":
                return
            sender = getattr(event, "sender", None)
            requesting_device_id = getattr(event, "requesting_device_id", None)
            room_id = getattr(event, "room_id", None) or getattr(getattr(event, "body", None), "room_id", None)
            session_id = getattr(event, "session_id", None) or getattr(getattr(event, "body", None), "session_id", None)
            logger.info(
                "room_key_request",
                sender=sender,
                device_id=requesting_device_id,
                room_id=room_id,
                session_id=session_id,
            )
            if self._cfg.matrix.trust_policy == "TOFU" and sender and requesting_device_id:
                try:
                    await client.share_group_session(
                        room_id,
                        [sender],
                        ignore_unverified_devices=True,
                    )
                    logger.info(
                        "room_key_reshared",
                        to=sender,
                        device_id=requesting_device_id,
                        session_id=session_id,
                    )
                except Exception as exc:
                    logger.warning("room_key_reshare_failed", error=str(exc))

    async def room_send_encrypted_or_plain(
        self,
        room_id: str,
        content: dict,
        msgtype: str = "m.room.message",
    ) -> nio.RoomSendResponse | nio.RoomSendError:
        client = self.client
        room = client.rooms.get(room_id)

        if room and room.encrypted:
            # Share group session keys if needed
            if client.should_upload_keys:
                await client.keys_upload()
            if client.should_query_keys:
                await client.keys_query()

            await client.share_group_session(room_id, ignore_unverified_devices=True)
            resp = await client.room_send(room_id, msgtype, content, ignore_unverified_devices=True)
        else:
            resp = await client.room_send(room_id, msgtype, content)

        return resp  # type: ignore[return-value]
