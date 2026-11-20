"""Video largo horizontal, enlaces short → largo y correcciones de texto."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_textnorm_tech_units():
    from explapix import textnorm
    t = textnorm.normalize("unos 3,7 V, 5000 mAh, 12 MP y GPS a 20 200 km")
    assert "voltios" in t and "miliamperios hora" in t and "megapíxeles" in t
    assert "veinte mil doscientos kilómetros" in t and "ge pe ese" in t
    assert not any(c.isdigit() for c in t)


def test_with_link_is_idempotent():
    from explapix import enlaces
    d = enlaces.with_link("Hola\n#FactosDidacticos", "https://youtu.be/abc")
    assert d.splitlines()[0] == "▶️ Video completo: https://youtu.be/abc"
    assert enlaces.with_link(d, "https://youtu.be/abc") == d
    assert enlaces.with_link(d, "https://youtu.be/xyz").count("Video completo") == 1


def test_long_storyboard_is_valid():
    lsb = json.loads((ROOT / "data/largos/tu-celular-por-dentro.json").read_text(encoding="utf-8"))
    cal = {it["id"] for it in json.loads((ROOT / "data/calendario.json").read_text(encoding="utf-8"))["items"]}
    shorts = [c["short_id"] for c in lsb["chapters"] if c.get("short_id")]
    assert len(shorts) >= 6 and set(shorts) <= cal
    segs = [s for c in lsb["chapters"] for s in c["segments"]]
    words = sum(len(s["narration"].split()) for s in segs)
    assert words / 2.6 >= 480, "debe pasar de 8 min para permitir anuncios a mitad"
    ctas = [s["cta"] for s in segs if s["cta"]]
    assert ctas.count("guardar") == 1 and len(ctas) <= 4
    g = next(s for s in segs if s["cta"] == "guardar")
    assert g["narration"].startswith("Guarda este video para")
    assert not any("uárdalo" in s["narration"] for s in segs)


def test_description_chapters_and_ad_breaks():
    ml = _load("make_long.py", "make_long")
    lsb = json.loads((ROOT / "data/largos/tu-celular-por-dentro.json").read_text(encoding="utf-8"))
    chapters = [{"title": c["title"], "start": 65.0 * k, "short_id": c.get("short_id")}
                for k, c in enumerate(lsb["chapters"])]
    desc = ml.build_description(lsb, chapters)
    assert "0:00 Intro" in desc and "1:05 La pantalla táctil" in desc
    total = 65.0 * len(chapters) + 20
    breaks = ml.ad_breaks(chapters, total, 120)
    assert breaks and all(b - a >= 120 for a, b in zip(breaks, breaks[1:]))
    assert breaks[0] >= 60 and total - breaks[-1] >= 60


def test_fix_guardalo_texts():
    fx = _load("scripts/corregir_y_enlazar.py", "corregir")
    t = fx.fix_text("💾 Guárdalo y mándaselo a alguien que no lo sabía.")
    assert "Guarda este video para" in t and "uárdalo" not in t


def test_scene_prompt_largo(monkeypatch):
    monkeypatch.setenv("EXPLAPIX_LLM", "api")
    from explapix import llm
    t = llm._scene_system_largo()
    assert "Lienzo HORIZONTAL" in t and "end_screen(20)" in t and "x∈[-7.4, 7.4]" in t
    assert "Reels/Shorts/TikTok, obligatorio" not in t
