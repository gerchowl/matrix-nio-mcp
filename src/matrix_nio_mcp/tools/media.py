"""Media upload/download tools."""

from __future__ import annotations

import mimetypes
from pathlib import Path

import aiofiles
import nio  # type: ignore[import-untyped]

from ..errors import MatrixNetworkError, raise_for_nio_response
from ..schemas import DownloadMediaInput, SendFileInput
from ..session import Session


async def send_file(session: Session, inp: SendFileInput) -> dict:
    file_path = Path(inp.file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {inp.file_path}")

    filename = inp.filename or file_path.name
    mimetype = inp.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_size = file_path.stat().st_size

    async with aiofiles.open(file_path, "rb") as f:
        data = await f.read()

    resp, _ = await session.client.upload(
        data,
        content_type=mimetype,
        filename=filename,
        filesize=file_size,
    )
    if isinstance(resp, nio.UploadError):
        raise_for_nio_response(resp)

    mxc_uri = resp.content_uri

    # Determine msgtype
    main_type = mimetype.split("/")[0]
    msgtype_map = {"image": "m.image", "video": "m.video", "audio": "m.audio"}
    msgtype = msgtype_map.get(main_type, "m.file")

    content = {
        "msgtype": msgtype,
        "body": filename,
        "url": mxc_uri,
        "info": {"size": file_size, "mimetype": mimetype},
    }
    if inp.caption:
        content["body"] = f"{inp.caption}\n{filename}"

    send_resp = await session.room_send_encrypted_or_plain(inp.room_id, content)
    if isinstance(send_resp, nio.RoomSendError):
        raise_for_nio_response(send_resp)

    return {"event_id": send_resp.event_id, "mxc_uri": mxc_uri}


async def download_media(session: Session, inp: DownloadMediaInput) -> dict:
    resp = await session.client.download(mxc=inp.mxc_uri)
    if isinstance(resp, nio.DownloadError):
        raise MatrixNetworkError(f"Download failed: {resp.message}")

    dest = Path(inp.dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(dest, "wb") as f:
        await f.write(resp.body)

    return {
        "dest_path": str(dest),
        "filename": resp.filename or dest.name,
        "size_bytes": len(resp.body),
    }
