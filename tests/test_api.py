"""Tests básicos del panel (sin GPU, sin red, sin YouTube). Correr: .venv/bin/python -m pytest -q"""
import base64
import importlib
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

VID = "20260101-1200-prueba-de-video"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    out, sec = tmp_path / "out", tmp_path / "secrets"
    (out / VID).mkdir(parents=True)
    sec.mkdir()
    (sec / "panel_password").write_text("clave-test\n")
    (sec / "client_secret.json").write_text("{}")
    d = out / VID
    sb = {"topic": "Prueba", "title": "Título", "description": "Desc", "tags": ["a"],
          "segments": [{"narration": "Hola", "visual": "Algo"}]}
    (d / "storyboard.json").write_text(json.dumps(sb))
    (d / "timing.json").write_text(json.dumps({"segments": [{"text": "Hola", "duration": 1.5}], "total": 1.5}))
    (d / "meta.json").write_text(json.dumps({"title": "Título", "description": "Desc", "tags": ["a"]}))
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=90x160:d=5",
                        "-pix_fmt", "yuv420p", str(d / "final.mp4")], check=True)
    else:
        (d / "final.mp4").write_bytes(b"\x00" * 2048)
    monkeypatch.setenv("EXPLAPIX_OUT", str(out))
    monkeypatch.setenv("EXPLAPIX_SECRETS_DIR", str(sec))
    monkeypatch.setenv("EXPLAPIX_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("EXPLAPIX_LLM", "api")
    cal = {"version": 1, "auto_generate": False, "items": [
        {"day": i + 1, "date": f"2026-11-0{i + 1}", "time": "13:00", "topic": f"Tema {i}", "hook": "h",
         "title": f"Título {i}", "ig_caption": "c", "pinned_comment": "p", "status": "pendiente",
         "video_id": None, "storyboard": {"topic": f"Tema {i}", "segments": []}} for i in range(3)]}
    (tmp_path / "cal.json").write_text(json.dumps(cal))
    monkeypatch.setenv("EXPLAPIX_CALENDAR", str(tmp_path / "cal.json"))
    import web.app as appmod
    appmod = importlib.reload(appmod)
    c = TestClient(appmod.app)  # sin "with": no arranca el worker de la cola
    c.auth = ("magne", "clave-test")
    c.mod, c.out = appmod, out
    return c


def test_requires_auth(client):
    assert TestClient(client.mod.app).get("/api/videos").status_code == 401
    bad = base64.b64encode(b"magne:mala").decode()
    assert TestClient(client.mod.app).get("/api/videos", headers={"Authorization": f"Basic {bad}"}).status_code == 401
    assert client.get("/").status_code == 200


def test_secrets_and_env_not_served(client):
    for p in ("/secrets/panel_password", "/.env", "/../secrets/panel_password",
              "/media/..%2Fsecrets/video.mp4", "/media/voces/..%2F..%2Fsecrets%2Fpanel_password"):
        r = client.get(p)
        assert r.status_code == 404, p
        assert "clave-test" not in r.text


def test_list_and_detail(client):
    vs = client.get("/api/videos").json()
    assert vs[0]["id"] == VID and vs[0]["status"] == "generado"
    d = client.get(f"/api/videos/{VID}").json()
    assert d["segments"][0]["duration"] == 1.5
    assert client.get("/api/videos/../../etc").status_code == 404


def test_video_range(client):
    r = client.get(f"/media/{VID}/video.mp4", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100


def test_review_and_meta(client):
    r = client.post(f"/api/videos/{VID}/review", json={"status": "rejected", "note": "Más humor"})
    assert r.json()["status"] == "rechazado"
    r = client.put(f"/api/videos/{VID}/meta", json={"title": "Nuevo", "description": "D", "tags": "x, y"})
    assert r.json()["title"] == "Nuevo"
    meta = json.loads((client.out / VID / "meta.json").read_text())
    assert meta["tags"] == ["x", "y"] and meta["review"]["note"] == "Más humor"
    assert client.put(f"/api/videos/{VID}/meta", json={"title": ""}).status_code == 422


def test_upload_needs_confirmation_and_token(client):
    assert client.post(f"/api/videos/{VID}/upload", json={"privacy": "public"}).status_code == 422
    r = client.post(f"/api/videos/{VID}/upload", json={"privacy": "private", "confirm": True})
    assert r.status_code == 409 and "YouTube" in r.json()["detail"]


def test_new_video_needs_key_and_queues(client):
    assert client.post("/api/jobs", json={"topics": "Microondas"}).status_code == 409
    assert client.put("/api/settings/anthropic", json={"key": "nope"}).status_code == 422
    assert client.put("/api/settings/anthropic", json={"key": "sk-ant-" + "x" * 30}).status_code == 200
    r = client.post("/api/jobs", json={"topics": "Microondas\nArcoíris", "engine": "kokoro"})
    assert r.status_code == 200 and len(r.json()) == 2
    jobs = client.get("/api/jobs").json()
    assert {j["status"] for j in jobs} == {"queued"} and "cmd" not in jobs[0]
    assert client.post(f"/api/jobs/{jobs[0]['id']}/cancel").json()["status"] == "cancelled"
    assert client.get("/api/status").json()["anthropic_key"] is True
    assert "sk-ant" not in client.get("/api/status").text


def test_voice_settings(client):
    assert client.put("/api/settings/voice", json={"EXPLAPIX_TTS": "nada"}).status_code == 422
    r = client.put("/api/settings/voice", json={"EXPLAPIX_TTS": "kokoro", "EXPLAPIX_CB_CFG": 0.5})
    assert r.json()["default_engine"] == "kokoro"


def test_comments_flow(client):
    drafts = [{"comment_id": "c1", "author": "Ana", "text": "¡Genial!", "reply": "Gracias",
               "skip": False, "approved": False, "sent": False}]
    (client.out / "comment_drafts.json").write_text(json.dumps(drafts))
    r = client.put("/api/comments/c1", json={"reply": "¡Gracias, Ana!", "approved": True})
    assert r.json()["approved"] is True
    assert client.post("/api/comments/send", json={}).status_code == 422
    assert client.post("/api/comments/send", json={"confirm": True}).status_code == 200


def test_delete_moves_to_trash(client):
    assert client.delete(f"/api/videos/{VID}").status_code == 200
    assert (client.out / "_papelera" / VID).exists()


def test_llm_engine_claude_code_needs_no_key(client, monkeypatch):
    monkeypatch.setenv("EXPLAPIX_LLM", "claude-code")
    st = client.get("/api/status").json()
    assert st["llm"] == "claude-code" and st["anthropic_key"] is False


def test_calendar_edit_reorder(client):
    cal = client.get("/api/calendar").json()
    ids = [it["id"] for it in cal["items"]]
    assert ids == ["tema-0", "tema-1", "tema-2"]
    r = client.put("/api/calendar/tema-1", json={"title": "Nuevo título", "status": "aprobado"})
    assert r.json()["title"] == "Nuevo título"
    assert client.put("/api/calendar/tema-1", json={"status": "inventado"}).status_code == 422
    r = client.post("/api/calendar/reorder", json={"order": ["tema-2", "tema-0", "tema-1"]}).json()
    assert [(i["id"], i["day"], i["date"]) for i in r["items"]][0] == ("tema-2", 1, "2026-11-01")
    assert client.post("/api/calendar/reorder", json={"order": ["tema-2"]}).status_code == 422
    assert client.put("/api/calendar/settings", json={"auto_generate": True}).json()["auto_generate"]
