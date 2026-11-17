"""Enlaces short → video largo (config/reglas.yaml, sección enlace_largo).

Cada video largo (data/largos/<id>.json) dice qué short corresponde a cada capítulo (short_id = id del
calendario). Cuando el largo ya está en YouTube (out/largo-<id>/meta.json → youtube_id), cada short lo
enlaza en la 1.ª línea de su descripción y en su comentario fijado. «Video relacionado» se pone a mano
en YouTube Studio (la API no lo permite).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LARGOS = ROOT / "data" / "largos"


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _param(key: str, default: str) -> str:
    r = yaml.safe_load((ROOT / "config" / "reglas.yaml").read_text(encoding="utf-8")) or {}
    return ((r.get("enlace_largo") or {}).get("parametros") or {}).get(key, default)


def largos() -> list[dict]:
    return [d for p in sorted(LARGOS.glob("*.json")) if (d := _read(p))]


def largo_url(largo_id: str) -> str:
    meta = _read(ROOT / "out" / f"largo-{largo_id}" / "meta.json", {}) or {}
    return f"https://youtu.be/{meta['youtube_id']}" if meta.get("youtube_id") else ""


def largo_for(short_id: str) -> tuple[str, str]:
    """(id del largo, url o "") del video largo que contiene ese short; ("", "") si ninguno."""
    for lsb in largos():
        if any(ch.get("short_id") == short_id for ch in lsb.get("chapters", [])):
            return lsb["id"], largo_url(lsb["id"])
    return "", ""


_LINE_RE = re.compile(r"^▶️? ?Video completo:.*\n?", re.M)


def with_link(text: str, url: str) -> str:
    """Pone «▶️ Video completo: <url>» como primera línea (sin duplicar)."""
    body = _LINE_RE.sub("", text or "").lstrip("\n")
    if not url:
        return body
    line = _param("linea_descripcion", "▶️ Video completo: {url}").format(url=url)
    return f"{line}\n{body}" if body else line


def apply(meta: dict, short_id: str) -> bool:
    """Marca el video/ítem con su largo y, si ya hay URL, enlaza descripción y comentario fijado.
    Sirve para un meta.json de out/ o para un ítem del calendario. Devuelve True si cambió algo."""
    lid, url = largo_for(short_id)
    if not lid:
        return False
    before = json.dumps(meta, ensure_ascii=False, sort_keys=True)
    meta["largo_id"], meta["largo_url"] = lid, url
    if url:
        if "description" in meta:
            meta["description"] = with_link(meta["description"], url)
        sb = meta.get("storyboard")
        if isinstance(sb, dict) and "description" in sb:
            sb["description"] = with_link(sb["description"], url)
        meta["pinned_comment"] = with_link(meta.get("pinned_comment", ""), url)
    return json.dumps(meta, ensure_ascii=False, sort_keys=True) != before
