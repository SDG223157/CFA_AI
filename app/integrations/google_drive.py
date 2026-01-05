from __future__ import annotations

import json
from typing import Any

import httpx


DRIVE_FILES_LIST_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_FILES_GET_URL = "https://www.googleapis.com/drive/v3/files/{file_id}"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def refresh_access_token(*, client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(GOOGLE_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()


def list_files(
    *,
    access_token: str,
    query: str = "",
    page_size: int = 20,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "pageSize": int(page_size),
        "fields": "files(id,name,mimeType,modifiedTime,size),nextPageToken",
    }
    if query.strip():
        # Drive query syntax: https://developers.google.com/drive/api/guides/search-files
        params["q"] = query.strip()
    with httpx.Client(timeout=30) as client:
        resp = client.get(DRIVE_FILES_LIST_URL, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()


def download_text(
    *,
    access_token: str,
    file_id: str,
    mime_type: str,
    max_bytes: int = 250_000,
) -> str:
    """
    Best-effort: returns UTF-8 text for common types.
    For Google Docs formats, uses export endpoints.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # Google native docs use export
    if mime_type.startswith("application/vnd.google-apps."):
        export_mime = "text/plain"
        if mime_type.endswith(".spreadsheet"):
            export_mime = "text/csv"
        url = DRIVE_FILES_GET_URL.format(file_id=file_id) + "/export"
        params = {"mimeType": export_mime}
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.content[:max_bytes]
            return data.decode("utf-8", errors="replace")

    # Regular files
    url = DRIVE_FILES_GET_URL.format(file_id=file_id)
    params = {"alt": "media"}
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.content[:max_bytes]
        return data.decode("utf-8", errors="replace")


def pack_credentials(*, refresh_token: str) -> str:
    return json.dumps({"refresh_token": refresh_token}, ensure_ascii=False)


def unpack_credentials(data: str) -> dict[str, Any]:
    try:
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


