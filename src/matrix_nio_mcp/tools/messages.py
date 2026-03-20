"""Messaging tools: send, react, redact, fetch, search."""

from __future__ import annotations

import re
from typing import Any

import nio  # type: ignore[import-untyped]

from ..errors import MatrixEncryptionError, MatrixRoomNotFound, raise_for_nio_response
from ..schemas import (
    GetEventInput,
    GetMessagesInput,
    Message,
    RedactEventInput,
    SearchMessagesInput,
    SearchResult,
    SendMessageInput,
    SendReactionInput,
)
from ..session import Session

_SIMPLE_MARKDOWN_RE = re.compile(r"\*\*(.+?)\*\*|`(.+?)`|_(.+?)_|\[(.+?)\]\((.+?)\)")


def _render_markdown(text: str) -> str:
    """Minimal Markdown → HTML (bold, inline code, italic, links)."""
    html = text
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)
    html = re.sub(r"_(.+?)_", r"<em>\1</em>", html)
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
    return html


def _event_to_message(event: Any) -> Message:
    body = ""
    formatted_body = None
    reply_to = None
    msg_type = "text"

    if isinstance(event, (nio.RoomMessageText, nio.RoomMessageNotice)):
        body = event.body
        formatted_body = getattr(event, "formatted_body", None)
        msg_type = "text" if isinstance(event, nio.RoomMessageText) else "notice"
        rel = getattr(event, "source", {}).get("content", {}).get("m.relates_to", {})
        reply_to = rel.get("m.in_reply_to", {}).get("event_id")
    elif isinstance(event, nio.RoomMessageImage):
        body = event.body
        msg_type = "image"
    elif isinstance(event, nio.RoomMessageFile):
        body = event.body
        msg_type = "file"
    elif isinstance(event, nio.RedactedEvent):
        body = "<redacted>"
        msg_type = "redacted"
    else:
        body = getattr(event, "body", str(event))

    return Message(
        event_id=event.event_id,
        sender=event.sender,
        timestamp=event.server_timestamp,
        type=msg_type,
        body=body,
        formatted_body=formatted_body,
        reply_to=reply_to,
    )


async def send_message(session: Session, inp: SendMessageInput) -> dict:
    content: dict[str, Any] = {"msgtype": "m.text", "body": inp.body}

    if inp.format == "markdown" and _SIMPLE_MARKDOWN_RE.search(inp.body):
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = _render_markdown(inp.body)

    if inp.reply_to_event_id:
        content["m.relates_to"] = {
            "m.in_reply_to": {"event_id": inp.reply_to_event_id}
        }

    resp = await session.room_send_encrypted_or_plain(inp.room_id, content)
    if isinstance(resp, nio.RoomSendError):
        raise_for_nio_response(resp)

    return {"event_id": resp.event_id, "timestamp": 0}


async def send_notice(session: Session, inp: SendMessageInput) -> dict:
    content: dict[str, Any] = {"msgtype": "m.notice", "body": inp.body}

    if inp.format == "markdown" and _SIMPLE_MARKDOWN_RE.search(inp.body):
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = _render_markdown(inp.body)

    resp = await session.room_send_encrypted_or_plain(inp.room_id, content)
    if isinstance(resp, nio.RoomSendError):
        raise_for_nio_response(resp)

    return {"event_id": resp.event_id, "timestamp": 0}


async def send_reaction(session: Session, inp: SendReactionInput) -> dict:
    content = {
        "m.relates_to": {
            "rel_type": "m.annotation",
            "event_id": inp.event_id,
            "key": inp.reaction,
        }
    }
    resp = await session.client.room_send(inp.room_id, "m.reaction", content)
    if isinstance(resp, nio.RoomSendError):
        raise_for_nio_response(resp)
    return {"event_id": resp.event_id}


async def redact_event(session: Session, inp: RedactEventInput) -> dict:
    resp = await session.client.room_redact(
        inp.room_id,
        inp.event_id,
        reason=inp.reason,
    )
    if isinstance(resp, nio.RoomRedactError):
        raise_for_nio_response(resp)
    return {"redaction_event_id": resp.event_id}


async def get_messages(session: Session, inp: GetMessagesInput) -> dict:
    resp = await session.client.room_messages(
        inp.room_id,
        start=inp.from_token or "",
        limit=inp.limit,
        direction=nio.MessageDirection.back if inp.direction == "backward" else nio.MessageDirection.front,
    )
    if isinstance(resp, nio.RoomMessagesError):
        raise_for_nio_response(resp)

    messages = [_event_to_message(e) for e in resp.chunk if not isinstance(e, nio.UnknownEvent)]
    return {
        "messages": [m.model_dump() for m in messages],
        "next_token": resp.end,
    }


async def get_event(session: Session, inp: GetEventInput) -> dict:
    resp = await session.client.room_get_event(inp.room_id, inp.event_id)
    if isinstance(resp, nio.RoomGetEventError):
        raise_for_nio_response(resp)
    return {"event": _event_to_message(resp.event).model_dump()}


async def search_messages(session: Session, inp: SearchMessagesInput) -> dict:
    search_categories: dict[str, Any] = {
        "room_events": {
            "search_term": inp.query,
            "order_by": "rank",
            "event_context": {"before_limit": 2, "after_limit": 2, "include_profile": False},
        }
    }
    if inp.room_ids:
        search_categories["room_events"]["filter"] = {
            "rooms": inp.room_ids,
            "limit": inp.limit,
        }

    resp = await session.client.search(search_categories)
    if isinstance(resp, nio.SearchError):
        raise_for_nio_response(resp)

    results = []
    for r in (resp.results or []):
        event = _event_to_message(r.result)
        before = [_event_to_message(e) for e in (r.context.events_before or [])]
        after = [_event_to_message(e) for e in (r.context.events_after or [])]
        results.append(
            SearchResult(rank=r.rank, event=event, context_before=before, context_after=after).model_dump()
        )

    return {"results": results}
