#!/usr/bin/env python3
"""Corrige los textos de los videos ya hechos y los enlaza con su video largo.

  python scripts/corregir_y_enlazar.py                  # vista previa: dice qué cambiaría, no toca nada
  python scripts/corregir_y_enlazar.py --aplicar        # escribe calendario y out/*/meta.json (local)
  python scripts/corregir_y_enlazar.py --aplicar --youtube
        # además, en los shorts YA subidos: cambia la descripción en YouTube y publica el comentario con el
        # enlace (fijarlo es a mano). Solo con la aprobación de Magne: cambia cosas públicas.

Qué corrige:
  1. «Guárdalo…» → «Guarda este video para…» en captions, descripciones y comentarios fijados
     (en la VOZ no se puede corregir con texto: el verificador marca esos videos para regenerar).
  2. Enlace al video largo (config/reglas.yaml → enlace_largo) en la 1.ª línea de la descripción y en el
     comentario fijado de cada short cuyo tema es capítulo de un largo.
Después vuelve a correr el verificador (sin Whisper; conserva el resultado de voz anterior).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from explapix import enlaces, qa  # noqa: E402

FIXES = [  # (patrón, reemplazo) para textos de redes; nunca «Guárdalo»
    (r"💾 Gu[aá]rdalo y mándaselo a alguien que no lo sabía\.",
     "💾 Guarda este video para tenerlo a mano y mándaselo a alguien que no lo sabía."),
    (r"💾 Gu[aá]rdalo para recordarlo y compártelo con alguien que no lo sabía\.",
     "💾 Guarda este video para recordarlo y compártelo con alguien que no lo sabía."),
    (r"\bGu[aá]rdalo para\b", "Guarda este video para"),
    (r"\bGu[aá]rdalo\b", "Guarda este video"),
    (r"\bgu[aá]rdalo para\b", "guarda este video para"),
    (r"\bgu[aá]rdalo\b", "guarda este video"),
]
TEXT_KEYS = ("ig_caption", "pinned_comment", "description")


def fix_text(t: str) -> str:
    for pat, rep in FIXES:
        t = re.sub(pat, rep, t)
    return t


def fix_record(rec: dict) -> list[str]:
    changed = []
    for k in TEXT_KEYS:
        if isinstance(rec.get(k), str) and fix_text(rec[k]) != rec[k]:
            rec[k] = fix_text(rec[k])
            changed.append(k)
    sb = rec.get("storyboard")
    if isinstance(sb, dict) and isinstance(sb.get("description"), str) and fix_text(sb["description"]) != sb["description"]:
        sb["description"] = fix_text(sb["description"])
        changed.append("storyboard.description")
    return changed


def voice_has_guardalo(sb: dict) -> bool:
    return any(re.search(r"gu[aá]rdal[oa]\b", s.get("narration", ""), re.I) for s in (sb or {}).get("segments", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--youtube", action="store_true", help="también actualizar shorts ya subidos (requiere aprobación)")
    a = ap.parse_args()
    calf = ROOT / "data" / "calendario.json"
    cal = json.loads(calf.read_text(encoding="utf-8"))
    regenerar = []
    print("== Calendario")
    for it in cal["items"]:
        ch = fix_record(it)
        if enlaces.apply(it, it["id"]):
            ch.append(f"enlace al largo ({it.get('largo_id')}{', ' + it['largo_url'] if it.get('largo_url') else ', sin URL aún'})")
        if voice_has_guardalo(it.get("storyboard")):
            regenerar.append(it["id"])
        if ch:
            print(f"  día {it['day']:2} {it['id']}: " + "; ".join(ch))
    if a.aplicar:
        calf.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== Videos (out/)")
    for d in sorted(p for p in (ROOT / "out").glob("2*") if (p / "meta.json").exists()):
        mf = d / "meta.json"
        meta = json.loads(mf.read_text(encoding="utf-8"))
        ch = fix_record(meta)
        cid = meta.get("calendar_id") or re.sub(r"^\d{8}-\d{4}-", "", d.name)
        if enlaces.apply(meta, cid):
            ch.append("enlace al largo" + ("" if meta.get("largo_url") else " (sin URL aún)"))
        sb = qa._json(d / "storyboard.json", {})
        if voice_has_guardalo(sb):
            regenerar.append(d.name)
        if not ch:
            continue
        print(f"  {d.name}: " + "; ".join(ch))
        if not a.aplicar:
            continue
        old = {c["id"]: c for c in (meta.get("qa") or {}).get("checks", [])}
        mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        res = qa.check(d, whisper=False)
        if "voz_transcripcion" in old:      # sin Whisper: conserva el resultado anterior de la voz
            res["checks"].append(old["voz_transcripcion"])
            res["ok"] = all(c["ok"] for c in res["checks"])
            res["passed"], res["total"] = sum(c["ok"] for c in res["checks"]), len(res["checks"])
        qa.save(d, res)
        meta = json.loads(mf.read_text(encoding="utf-8"))
        if a.youtube and meta.get("youtube_id") and meta.get("largo_url") and not meta.get("largo_enlazado_yt"):
            from explapix import youtube  # noqa: PLC0415
            youtube.update_description(meta["youtube_id"], meta["description"])
            youtube.comment(meta["youtube_id"], meta["pinned_comment"])
            meta["largo_enlazado_yt"] = True
            mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    YouTube actualizado (fija el comentario y pon «Video relacionado» en Studio)")
    if regenerar:
        print("== Dicen «Guárdalo» en la VOZ (regenerar con «Versión extendida» o «Regenerar»):")
        for x in sorted(set(regenerar)):
            print("  " + x)
    if not a.aplicar:
        print("\n(vista previa: no se cambió nada; usa --aplicar)")


if __name__ == "__main__":
    main()
