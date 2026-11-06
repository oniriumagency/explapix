"""Subida a YouTube (Shorts) y gestión de comentarios con la YouTube Data API v3.

Cuota gratuita: 10 000 unidades/día. Subir un video = ~1600, listar comentarios = 1,
responder = 50. Alcanza para ~5 videos diarios y cientos de respuestas.

Configuración única:
 1. Google Cloud Console -> crear proyecto -> habilitar "YouTube Data API v3".
 2. Pantalla de consentimiento OAuth (externa, agrega tu cuenta como usuario de prueba).
 3. Credenciales -> ID de cliente OAuth "App de escritorio" -> descargar como client_secret.json.
 4. La primera ejecución abre el navegador para autorizar; el token queda en token.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
SECRETS = Path(os.environ.get("EXPLAPIX_YT_SECRETS", "secrets/client_secret.json"))
TOKEN = Path(os.environ.get("EXPLAPIX_YT_TOKEN", "secrets/token.json"))


def service():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:  # en un servidor sin pantalla: copia la URL que imprime en tu navegador
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
            creds = flow.run_local_server(port=8765, open_browser=False)
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, title: str, description: str, tags: list[str],
           privacy: str = "private", publish_at: str | None = None) -> str:
    """Sube el video. privacy: private | unlisted | public. publish_at ISO8601 programa la salida."""
    if "#shorts" not in description.lower():
        description += "\n#Shorts"
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}  # voz sintética: declaración de contenido alterado
    if publish_at:
        status.update(privacyStatus="private", publishAt=publish_at)
    body = {"snippet": {"title": title[:100], "description": description[:5000], "tags": tags,
                        "categoryId": "27", "defaultLanguage": "es",
                        "defaultAudioLanguage": "es"},
            "status": status}
    req = service().videos().insert(part="snippet,status", body=body,
                                    media_body=MediaFileUpload(str(video), chunksize=-1,
                                                               resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def channel_id(yt) -> str:
    return yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]


def unanswered_comments(max_threads: int = 100) -> list[dict]:
    """Hilos de comentarios del canal donde el canal todavía no respondió."""
    yt = service()
    me = channel_id(yt)
    out, token = [], None
    while len(out) < max_threads:
        r = yt.commentThreads().list(part="snippet,replies", allThreadsRelatedToChannelId=me,
                                     maxResults=50, order="time", textFormat="plainText",
                                     pageToken=token).execute()
        for th in r.get("items", []):
            top = th["snippet"]["topLevelComment"]
            if top["snippet"].get("authorChannelId", {}).get("value") == me:
                continue
            replies = th.get("replies", {}).get("comments", [])
            if any(c["snippet"].get("authorChannelId", {}).get("value") == me for c in replies):
                continue
            out.append({"thread_id": th["id"], "comment_id": top["id"],
                        "video_id": th["snippet"]["videoId"],
                        "author": top["snippet"]["authorDisplayName"],
                        "text": top["snippet"]["textDisplay"]})
        token = r.get("nextPageToken")
        if not token:
            break
    return out


def video_info(video_id: str) -> dict:
    items = service().videos().list(part="snippet", id=video_id).execute()["items"]
    return items[0]["snippet"] if items else {"title": "", "description": ""}


def reply(parent_comment_id: str, text: str) -> str:
    r = service().comments().insert(part="snippet", body={
        "snippet": {"parentId": parent_comment_id, "textOriginal": text}}).execute()
    return r["id"]


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
