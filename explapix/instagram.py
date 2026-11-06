"""Instagram (API de Instagram con inicio de sesión de Instagram, de Meta).

Permisos: instagram_business_basic, instagram_business_content_publish,
instagram_business_manage_comments, instagram_business_manage_insights.
Requiere una cuenta de Instagram profesional (empresa o creador).

Publicar un Reel: Meta descarga el video desde una URL pública. Lo servimos solo durante la
subida con Tailscale Funnel (public_video_url), en una ruta aleatoria, y la cerramos al terminar.

Credenciales en secrets/instagram.json (permisos 600):
  {"app_id", "app_secret", "redirect_uri", "access_token", "user_id", "username", "expires_at",
   "token_created"}
El token de larga duración dura 60 días; refresh_if_needed() lo renueva solo cuando faltan <10 días.
"""
from __future__ import annotations

import http.server
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDS = Path(os.environ.get("EXPLAPIX_IG_CREDS", ROOT / "secrets" / "instagram.json"))
GRAPH = "https://graph.instagram.com/v23.0"
SCOPES = ["instagram_business_basic", "instagram_business_content_publish",
          "instagram_business_manage_comments", "instagram_business_manage_insights"]
FUNNEL_PORT = int(os.environ.get("EXPLAPIX_FUNNEL_PORT", "8099"))


# ------------------------------------------------------------------ credenciales
def load() -> dict:
    try:
        return json.loads(CREDS.read_text())
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    CREDS.parent.mkdir(parents=True, exist_ok=True)
    CREDS.write_text(json.dumps(data, indent=1))
    CREDS.chmod(0o600)


def connected() -> bool:
    c = load()
    return bool(c.get("access_token") and c.get("user_id"))


def _http(method: str, url: str, params: dict | None = None, timeout: int = 120) -> dict:
    data = None
    if params and method == "GET":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Instagram API {e.code}: {body[:500]}") from e


# ------------------------------------------------------------------ OAuth
def auth_url(state: str) -> str:
    c = load()
    if not c.get("app_id") or not c.get("redirect_uri"):
        raise RuntimeError("Falta el App ID o la URL de redirección de Instagram")
    q = {"client_id": c["app_id"], "redirect_uri": c["redirect_uri"], "response_type": "code",
         "scope": ",".join(SCOPES), "state": state, "enable_fb_login": "0", "force_reauth": "true"}
    return "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode(q)


def exchange_code(code: str) -> dict:
    """Código -> token corto -> token largo (60 días). Guarda user_id y username."""
    c = load()
    code = code.split("#")[0]
    short = _http("POST", "https://api.instagram.com/oauth/access_token", {
        "client_id": c["app_id"], "client_secret": c["app_secret"], "grant_type": "authorization_code",
        "redirect_uri": c["redirect_uri"], "code": code})
    long = _http("GET", "https://graph.instagram.com/access_token", {
        "grant_type": "ig_exchange_token", "client_secret": c["app_secret"],
        "access_token": short["access_token"]})
    me = _http("GET", f"{GRAPH}/me", {"fields": "user_id,username", "access_token": long["access_token"]})
    c.update(access_token=long["access_token"], user_id=str(me.get("user_id") or short.get("user_id")),
             username=me.get("username", ""), expires_at=int(time.time()) + int(long.get("expires_in", 5184000)),
             token_created=int(time.time()))
    save(c)
    return {"username": c["username"], "expires_at": c["expires_at"]}


def refresh_if_needed(min_days: float = 10) -> bool:
    c = load()
    if not c.get("access_token"):
        return False
    left = c.get("expires_at", 0) - time.time()
    if left > min_days * 86400 or time.time() - c.get("token_created", 0) < 86400:
        return False
    r = _http("GET", "https://graph.instagram.com/refresh_access_token",
              {"grant_type": "ig_refresh_token", "access_token": c["access_token"]})
    c.update(access_token=r["access_token"], expires_at=int(time.time()) + int(r.get("expires_in", 5184000)),
             token_created=int(time.time()))
    save(c)
    return True


def _tok() -> tuple[str, str]:
    refresh_if_needed()
    c = load()
    if not c.get("access_token"):
        raise RuntimeError("Instagram no está conectado (Sistema → Conectar Instagram)")
    return c["access_token"], c["user_id"]


# ------------------------------------------------------------------ URL pública temporal
def _tailscale() -> str:
    return shutil.which("tailscale") or "tailscale"


def _dns_name() -> str:
    out = subprocess.run([_tailscale(), "status", "--self", "--json"], capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out)["Self"]["DNSName"].rstrip(".")


@contextmanager
def public_video_url(video: Path):
    """Sirve SOLO este archivo en https://<servidor>.ts.net/<ruta-aleatoria>/video.mp4 mientras dura el
    bloque, con Tailscale Funnel. Requiere Funnel habilitado en el tailnet y que el usuario sea
    operador de tailscale (sudo tailscale set --operator=$USER, una vez)."""
    token = secrets.token_urlsafe(18)
    size = video.stat().st_size

    class One(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if not self.path.rstrip("/").endswith("video.mp4"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(video, "rb") as f:
                shutil.copyfileobj(f, self.wfile)

        do_HEAD = do_GET  # noqa: N815

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", FUNNEL_PORT), One)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    path = f"/{token}"
    p = subprocess.run([_tailscale(), "funnel", "--bg", "--yes", f"--set-path={path}",
                        f"http://127.0.0.1:{FUNNEL_PORT}"], capture_output=True, text=True)
    try:
        if p.returncode != 0:
            raise RuntimeError("No pude abrir Tailscale Funnel. Habilítalo en el panel de Tailscale "
                               "(HTTPS + Funnel) y ejecuta una vez: sudo tailscale set --operator=$USER\n"
                               + (p.stderr or p.stdout)[-400:])
        yield f"https://{_dns_name()}{path}/video.mp4"
    finally:
        subprocess.run([_tailscale(), "funnel", f"--set-path={path}", "off"], capture_output=True, text=True)
        srv.shutdown()


# ------------------------------------------------------------------ publicar
def publish_reel(video: Path, caption: str, share_to_feed: bool = True, log=print) -> dict:
    token, uid = _tok()
    with public_video_url(video) as url:
        log(f"   URL temporal lista; Meta está descargando el video…")
        cont = _http("POST", f"{GRAPH}/{uid}/media", {"media_type": "REELS", "video_url": url,
                                                       "caption": caption[:2200],
                                                       "share_to_feed": "true" if share_to_feed else "false",
                                                       "access_token": token})
        cid = cont["id"]
        for _ in range(120):  # hasta ~10 min
            st = _http("GET", f"{GRAPH}/{cid}", {"fields": "status_code,status", "access_token": token})
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Meta no pudo procesar el video: {st}")
            time.sleep(5)
        else:
            raise RuntimeError("Meta tardó demasiado en procesar el video")
    pub = _http("POST", f"{GRAPH}/{uid}/media_publish", {"creation_id": cid, "access_token": token})
    info = _http("GET", f"{GRAPH}/{pub['id']}", {"fields": "permalink,shortcode", "access_token": token})
    return {"id": pub["id"], "permalink": info.get("permalink")}


def pin_comment_hint() -> str:
    return "La API no permite fijar comentarios: publícalo como respuesta y fíjalo desde la app."


# ------------------------------------------------------------------ comentarios
def recent_media(limit: int = 20) -> list[dict]:
    token, uid = _tok()
    r = _http("GET", f"{GRAPH}/{uid}/media", {"fields": "id,caption,permalink,timestamp", "limit": limit,
                                               "access_token": token})
    return r.get("data", [])


def unanswered_comments(max_media: int = 20) -> list[dict]:
    token, uid = _tok()
    me = load().get("username", "")
    out = []
    for m in recent_media(max_media):
        r = _http("GET", f"{GRAPH}/{m['id']}/comments", {
            "fields": "id,text,username,timestamp,replies{username}", "limit": 50, "access_token": token})
        for c in r.get("data", []):
            if c.get("username") == me:
                continue
            if any(x.get("username") == me for x in c.get("replies", {}).get("data", [])):
                continue
            out.append({"platform": "instagram", "comment_id": c["id"], "video_id": m["id"],
                        "author": c.get("username", ""), "text": c.get("text", ""),
                        "video_title": (m.get("caption") or "").split("\n")[0][:100],
                        "video_description": m.get("caption") or ""})
    return out


def reply(comment_id: str, text: str) -> str:
    token, _ = _tok()
    return _http("POST", f"{GRAPH}/{comment_id}/replies", {"message": text, "access_token": token})["id"]


# ------------------------------------------------------------------ métricas
INSIGHTS = ["reach", "views", "saved", "shares", "likes", "comments", "total_interactions",
            "ig_reels_avg_watch_time"]


def media_insights(media_id: str) -> dict:
    token, _ = _tok()
    out = {}
    for metric in INSIGHTS:  # de uno en uno: si una métrica no aplica, las demás siguen
        try:
            r = _http("GET", f"{GRAPH}/{media_id}/insights", {"metric": metric, "access_token": token})
            for d in r.get("data", []):
                v = d.get("values", [{}])[0].get("value", d.get("total_value", {}).get("value"))
                out[d["name"]] = v
        except RuntimeError:
            continue
    return out
