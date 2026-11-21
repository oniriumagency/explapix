"""Guiones escritos a mano para el calendario (data/guiones/lote-*.yaml).

Valida cada guion contra config/reglas.yaml (duración estimada, capítulos, CTA, números en palabras,
nunca «Guárdalo») y, con --aplicar, los agrega al final de data/calendario.json como «pendiente»,
con fecha y hora a continuación del último día. No toca ítems existentes ni repite temas (por id).

  .venv/bin/python scripts/guiones_lote.py              # solo valida y muestra el resumen
  .venv/bin/python scripts/guiones_lote.py --aplicar    # valida y agrega al calendario

Formato de cada guion (YAML):
  id, topic, category, hook, title, summary (valor para captions), question (la del CTA de comentar),
  pinned (comentario fijado), hashtags (2-3 de nicho), justificacion, tags (opcional),
  segments: lista de {b: beat, n: narración, v: visual, ch: mini-título (opcional), cta: tipo (opcional)}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "guiones"
CAL = ROOT / "data" / "calendario.json"
REGLAS = yaml.safe_load((ROOT / "config" / "reglas.yaml").read_text(encoding="utf-8"))

# horario por día de la semana (lunes=0), igual que el calendario base
HORAS = {0: "19:30", 1: "13:00", 2: "19:30", 3: "13:00", 4: "20:00", 5: "11:00", 6: "12:00"}
BEATS = {"gancho", "promesa", "beat1", "beat2", "beat3", "beat4", "dato_extra", "cierre"}
CTAS = {"guardar", "compartir", "comentar", "seguir", "like"}
# siglas que explapix/textnorm.py ya sabe leer
SIGLAS_OK = {"GPS", "QR", "UV", "UVA", "UVB", "ADN", "ARN", "NFC", "USB", "LED", "CPU", "PIN", "SIM", "TV"}


def _p(sec: str, key: str, default=None):
    return ((REGLAS.get(sec) or {}).get("parametros") or {}).get(key, default)


WPS = _p("guion", "palabras_por_segundo", 2.6)
PAUSA = (_p("voz", "pausas", {}) or {})
DMIN, DMAX = _p("guion", "duracion_min_s", 61), _p("guion", "duracion_max_s", 175)
FRASE_G = _p("cta", "guardar_frase", "Guarda este video para")
PROHIBIDO_G = _p("cta", "guardar_prohibido", [r"gu[aá]rdal[oa]\b"])
CEBO = _p("cta", "cebo_prohibido", [])
TAG = _p("marca", "hashtag", "#FactosDidacticos")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def seg_dur(text: str) -> float:
    """Segundos estimados de un segmento: palabras a 2,6 por segundo + pausas de puntuación."""
    w = len(text.split())
    p = (text.count(",") * PAUSA.get("coma", 0.18) + len(re.findall(r"[.:;]", text)) * PAUSA.get("punto", 0.35)
         + len(re.findall(r"[?!]", text)) * PAUSA.get("pregunta", 0.45))
    return w / WPS + p + PAUSA.get("fin_segmento", 0.5)


def frase_con(text: str, pat: str) -> str:
    for f in re.split(r"(?<=[.!?])\s+", text):
        if re.search(pat, f, re.I):
            return f
    return ""


def validar(g: dict) -> tuple[list[str], dict]:
    err: list[str] = []
    segs = g.get("segments") or []
    for k in ("id", "topic", "category", "hook", "title", "summary", "question", "pinned", "hashtags",
              "justificacion"):
        if not g.get(k):
            err.append(f"falta {k}")
    if not 8 <= len(segs) <= 28:
        err.append(f"{len(segs)} segmentos (8-28)")
    durs = [seg_dur(s["n"]) for s in segs]
    total = sum(durs) or 1
    starts = [sum(durs[:i]) for i in range(len(segs))]
    if not DMIN + 6 <= total <= DMAX - 10:          # margen: la voz real varía unos segundos
        err.append(f"duración estimada {total:.0f} s fuera de {DMIN + 6}-{DMAX - 10}")
    n_ch = sum(1 for s in segs if s.get("ch"))
    if total > 75 and not 2 <= n_ch <= 4:            # margen: si la voz real pasa de 90 s, ya trae capítulos
        err.append(f"{total:.0f} s y {n_ch} capítulos (2-4)")
    if segs and segs[0].get("ch"):
        err.append("el gancho no lleva capítulo")
    for i, s in enumerate(segs):
        n = s["n"]
        if s.get("b") not in BEATS:
            err.append(f"seg {i}: beat {s.get('b')!r}")
        if s.get("cta") and s["cta"] not in CTAS:
            err.append(f"seg {i}: cta {s['cta']!r}")
        w = len(n.split())
        if not 11 <= w <= 28:
            err.append(f"seg {i}: {w} palabras")
        if re.search(r"\d|[°%$€#@&/+=×]", n):
            err.append(f"seg {i}: número o símbolo sin pasar a palabras: {n}")
        for sig in re.findall(r"\b[A-ZÁÉÍÓÚÑ]{2,}\b", n):
            if sig not in SIGLAS_OK:
                err.append(f"seg {i}: sigla {sig} (escríbela como se lee)")
        if not s.get("v"):
            err.append(f"seg {i}: falta visual")
    # CTA (mismas ventanas que explapix/qa.py)
    ctas = [(i, s["cta"], starts[i] / total, s["n"]) for i, s in enumerate(segs) if s.get("cta")]
    if not 1 <= len(ctas) <= _p("cta", "max_hablados", 3):
        err.append(f"{len(ctas)} CTA")
    if any(starts[i] < _p("cta", "sin_cta_antes_de_s", 5) for i, *_ in ctas):
        err.append("CTA antes de 5 s")
    gd = [c for c in ctas if c[1] == "guardar"]
    w0, w1 = _p("cta", "guardar_ventana", [0.2, 0.42])
    if not gd or FRASE_G.lower() not in gd[0][3].lower() or not w0 + 0.02 <= gd[0][2] <= w1 - 0.02:
        err.append(f"CTA guardar: {[(round(c[2], 2), c[3]) for c in gd] or 'no hay'}")
    elif len(frase_con(gd[0][3], FRASE_G).split()) > 8:
        err.append(f"CTA guardar de más de 8 palabras: {frase_con(gd[0][3], FRASE_G)}")
    cm = [c for c in ctas if c[1] == "comentar"]
    c0, c1 = _p("cta", "comentar_ventana", [0.45, 0.72])
    if not cm or "?" not in cm[0][3] or not c0 + 0.02 <= cm[0][2] <= c1 - 0.02:
        err.append(f"CTA comentar: {[(round(c[2], 2), c[3]) for c in cm] or 'no hay'}")
    else:
        q = re.findall(r"¿[^?]+\?", cm[0][3])
        if not q or len(q[-1].split()) > 8:
            err.append(f"pregunta de comentar de más de 8 palabras: {q}")
    fin = [c for c in ctas if c[1] in ("compartir", "seguir")]
    if not fin or fin[-1][2] < _p("cta", "final_desde", 0.7) + 0.02 or fin[-1][0] == len(segs) - 1:
        err.append("CTA final (compartir/seguir) después del 70 % y antes de la última frase")
    else:
        f = frase_con(fin[-1][3], r"^(síguenos|mándaselo|compártelo|comparte|la versión)")
        if f and len(f.split()) > 8:
            err.append(f"CTA final de más de 8 palabras: {f}")
    # textos
    todo = " ".join([json.dumps(g, ensure_ascii=False)])
    if any(re.search(p, todo, re.I) for p in PROHIBIDO_G):
        err.append("aparece «Guárdalo»")
    if any(re.search(p, todo, re.I) for p in CEBO):
        err.append("cebo de interacción")
    if re.search(r"explapix", todo, re.I):
        err.append("nombre interno en el texto")
    if len(g.get("title", "")) > 60:
        err.append(f"título de {len(g['title'])} caracteres")
    if g.get("id") and g["id"] != slug(g["topic"]):
        err.append(f"id {g['id']} ≠ {slug(g['topic'])}")
    return err, {"total": total, "words": sum(len(s["n"].split()) for s in segs), "segs": len(segs),
                 "chapters": n_ch}


def storyboard(g: dict, total: float) -> dict:
    tags = g.get("tags") or [g["topic"].lower(), g["category"], "ciencia", "como funciona", "datos curiosos",
                             "shorts"]
    hashtags = [TAG] + [h for h in g["hashtags"] if h != TAG]
    desc = (f"{g['hook']}\n💾 {FRASE_G} {g.get('guardar_para', 'tenerlo a mano')}.\n\n{g['summary']}\n\n"
            f"{g['question']}\n\n" + " ".join(hashtags[:5]))
    return {
        "topic": g["topic"], "title": g["title"], "description": desc, "tags": tags,
        "duracion_objetivo_s": int(round(total)), "justificacion_duracion": g["justificacion"],
        "segments": [{"narration": s["n"], "visual": s["v"], "beat": s["b"], "chapter": s.get("ch", ""),
                      "cta": s.get("cta", "")} for s in g["segments"]],
    }


def item(g: dict, total: float) -> dict:
    hashtags = [TAG] + [h for h in g["hashtags"] if h != TAG] + ["#ciencia", "#datoscuriosos"]
    hashtags = list(dict.fromkeys(hashtags))[:5]
    cap = (f"{g['hook']} 🤯\n💾 {FRASE_G} {g.get('guardar_para', 'tenerlo a mano')} y mándaselo a alguien que no "
           f"lo sabía.\n\n{g['summary']}\n\n{g['question']} 👇\n\n" + " ".join(hashtags))
    return {"topic": g["topic"], "category": g["category"], "hook": g["hook"], "title": g["title"],
            "ig_caption": cap, "summary": g["summary"], "pinned_comment": g["pinned"], "hashtags": hashtags,
            "status": "pendiente", "video_id": None, "notes": "", "id": g["id"], "storyboard": storyboard(g, total),
            "origen": "guiones a mano (data/guiones)"}


def cargar() -> list[dict]:
    out = []
    for f in sorted(SRC.glob("lote-*.yaml")):
        for g in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            g["_file"] = f.name
            out.append(g)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="agregar al calendario")
    ap.add_argument("--calendario", type=Path, default=CAL)
    a = ap.parse_args()
    gs = cargar()
    malos, filas = 0, []
    ids = [g.get("id") for g in gs]
    dup = {i for i in ids if ids.count(i) > 1}
    for g in gs:
        err, st = validar(g)
        if g.get("id") in dup:
            err.append("id repetido en los lotes")
        filas.append((g, st))
        flag = "OK " if not err else "ERR"
        print(f"{flag} {st['total']:5.0f} s {st['words']:4d} pal {st['segs']:2d} seg {st['chapters']} cap  "
              f"{g['_file']}  {g.get('topic')}")
        for e in err:
            print("     -", e)
        malos += bool(err)
    tot = [st["total"] for _, st in filas]
    if tot:
        print(f"\n{len(gs)} guiones, {malos} con problemas; duración estimada {min(tot):.0f}-{max(tot):.0f} s "
              f"(media {sum(tot) / len(tot):.0f} s)")
    if malos:
        return 1
    if not a.aplicar:
        return 0
    cal = json.loads(a.calendario.read_text(encoding="utf-8"))
    items = cal["items"]
    have = {it.get("id") or slug(it["topic"]) for it in items}
    have_topics = {it["topic"].lower() for it in items}
    last = max(items, key=lambda x: x["day"]) if items else None
    day = last["day"] if last else 0
    d = date.fromisoformat(last["date"]) if last else date.today()
    tz = last.get("tz", "America/Mexico_City") if last else "America/Mexico_City"
    added = 0
    for g, st in filas:
        if g["id"] in have or g["topic"].lower() in have_topics:
            print("ya está en el calendario:", g["topic"])
            continue
        day += 1
        d += timedelta(days=1)
        items.append({"day": day, "date": d.isoformat(), "time": HORAS[d.weekday()], "tz": tz,
                      **item(g, st["total"])})
        added += 1
    a.calendario.write_text(json.dumps(cal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"agregados {added} temas al calendario ({a.calendario}); último día {day} ({d.isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
