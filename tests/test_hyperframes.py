"""Motor alternativo HyperFrames: selección de motor, panel y configuración de la escena (sin Chrome ni render)."""
import json
from pathlib import Path

import pytest

from explapix import hyperframes, render

from tests.test_api import VID, client  # noqa: F401  (fixture del panel)


def test_motor_by_scene_suffix(tmp_path):
    assert render.motor_of(Path("x/scene.js")) == "hyperframes"
    assert render.motor_of(Path("x/scene.py")) == "manim"
    assert render.motor_of(None) == "manim"
    assert render.scene_file(tmp_path) is None
    (tmp_path / "scene.py").write_text("")
    assert render.scene_file(tmp_path).name == "scene.py"
    (tmp_path / "scene.js").write_text("")
    assert render.scene_file(tmp_path).name == "scene.js"


def test_motor_default(monkeypatch):
    monkeypatch.delenv("EXPLAPIX_MOTOR", raising=False)
    assert render.motor_default() == "manim"
    monkeypatch.setenv("EXPLAPIX_MOTOR", "hyperframes")
    assert render.motor_default() == "hyperframes"
    monkeypatch.setenv("EXPLAPIX_MOTOR", "otro")
    assert render.motor_default() == "manim"


def test_hyperframes_no_horizontal(tmp_path):
    ok, log, out = render.render_scene(tmp_path / "scene.js", tmp_path, "hd", formato="largo")
    assert not ok and out is None and "horizontal" in log


def test_config_reads_rules(tmp_path):
    (tmp_path / "timing.json").write_text(json.dumps({"segments": [
        {"text": "Hola", "duration": 2.0}, {"text": "Guarda este video para luego.", "duration": 3.5}]}))
    (tmp_path / "storyboard.json").write_text(json.dumps({"segments": [{"cta": ""}, {"cta": "guardar"}]}))
    cfg = hyperframes.config_for(tmp_path)
    assert cfg["duracion"] == 5.5
    assert [s["cta"] for s in cfg["segmentos"]] == ["", "guardar"]
    assert cfg["zona"] == {"arriba": 0.12, "abajo": 0.20, "derecha": 0.15, "izquierda": 0.05}
    assert 0.5 < cfg["botones_altura"] < 0.8


def test_layout_problems(tmp_path):
    assert hyperframes.layout_problems(tmp_path) == ""
    (tmp_path / "layout.json").write_text(json.dumps({"fuera": [{"t": 1.5, "texto": "Hola", "borde": "arriba"}]}))
    assert "«Hola»" in hyperframes.layout_problems(tmp_path)


def test_example_scene_is_valid_js():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("sin node")
    root = Path(__file__).resolve().parent.parent
    for f in (root / "examples" / "microondas" / "scene.js", root / "hyperframes" / "kit.js"):
        assert subprocess.run([node, "--check", str(f)]).returncode == 0, f


def test_panel_motor_choice(client, monkeypatch):  # noqa: F811
    client.put("/api/settings/anthropic", json={"key": "sk-ant-" + "x" * 30})
    assert client.post("/api/jobs", json={"topics": "Microondas", "motor": "otro"}).status_code == 422
    monkeypatch.setattr(hyperframes, "ready", lambda: (False, "falta node"))
    r = client.post("/api/jobs", json={"topics": "Microondas", "motor": "hyperframes"})
    assert r.status_code == 409 and "falta node" in r.text
    monkeypatch.setattr(hyperframes, "ready", lambda: (True, ""))
    r = client.post("/api/jobs", json={"topics": "Microondas", "motor": "hyperframes"})
    assert r.status_code == 200
    job = client.mod.jobs.jobs[-1]
    assert job["cmd"][-2:] == ["--motor", "hyperframes"]
    st = client.get("/api/status").json()
    assert st["hyperframes"]["ready"] is True and st["hyperframes"]["default_motor"] == "manim"


def test_panel_shows_js_scene(client):  # noqa: F811
    d = client.out / VID
    (d / "scene.js").write_text("function escena(k) {}\n")
    v = client.get(f"/api/videos/{VID}").json()
    assert v["motor"] == "hyperframes" and "function escena" in v["scene"]
