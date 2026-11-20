#!/usr/bin/env python3
"""Video largo horizontal (16:9) para YouTube: un capítulo por tema, cada uno ligado a su short.

  python make_long.py data/largos/tu-celular-por-dentro.json             # todo (retoma lo ya hecho)
  python make_long.py data/largos/tu-celular-por-dentro.json --quality draft
  python make_long.py data/largos/tu-celular-por-dentro.json --redo 03-bateria   # rehace un capítulo
  python make_long.py data/largos/tu-celular-por-dentro.json --textos     # solo descripción/capítulos

Cada capítulo se narra y se anima por separado (out/<largo>/caps/NN-id/), así un fallo o un límite de
uso no obliga a rehacer todo: lo que ya está renderizado y no cambió se reutiliza. Al final se unen
los capítulos, se mezcla el audio una sola vez, se escriben los capítulos de YouTube en la descripción,
las pausas sugeridas para anuncios y la pantalla final, y corre el verificador (config/reglas.yaml).

Escenas escritas a mano: data/largos/<id>/<NN-id>.py (tienen prioridad sobre las de Claude).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from explapix import render, tts

ROOT = Path(__file__).resolve().parent
FORMATO = "largo"


def _mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def _write(p: Path, data) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def chapter_dirs(lsb: dict, work: Path) -> list[tuple[int, dict, Path]]:
    return [(k, ch, work / "caps" / f"{k:02d}-{ch['id']}") for k, ch in enumerate(lsb["chapters"])]


def short_links(lsb: dict) -> dict[str, str]:
    """URL de YouTube de cada short del largo, si ya está subido (out/<video>/meta.json → youtube_id)."""
    cal = _read(ROOT / "data" / "calendario.json", {}) or {}
    by_id = {it.get("id"): it for it in cal.get("items", [])}
    out = {}
    for ch in lsb["chapters"]:
        sid = ch.get("short_id")
        it = by_id.get(sid) or {}
        vid = it.get("video_id")
        meta = _read(ROOT / "out" / vid / "meta.json", {}) if vid else {}
        yid = (meta or {}).get("youtube_id") or it.get("youtube_id")
        if sid and yid:
            out[sid] = f"https://youtube.com/shorts/{yid}"
    return out


def build_description(lsb: dict, chapters: list[dict]) -> str:
    links = short_links(lsb)
    lines = [lsb["description"].strip(), "", "⏱️ Capítulos"]
    lines += [f"{_mmss(c['start'])} {c['title']}" for c in chapters]
    shorts = [(c["title"], links[c["short_id"]]) for c in chapters if c.get("short_id") in links]
    if shorts:
        lines += ["", "📱 Cada tema en un minuto:"] + [f"• {t}: {u}" for t, u in shorts]
    lines += ["", " ".join(lsb.get("hashtags") or ["#FactosDidacticos"])]
    return "\n".join(lines)


def ad_breaks(chapters: list[dict], total: float, gap: float) -> list[float]:
    """Inicios de capítulo como pausas para anuncios: después del primer minuto, separados ≥ gap s y
    no en el último minuto (YouTube los permite desde 8:00 de duración)."""
    out, last = [], 0.0
    for c in chapters[1:]:
        t = c["start"]
        if t >= 60 and t - last >= gap and total - t >= 60:
            out.append(t)
            last = t
    return out


def build_chapter(k: int, ch: dict, d: Path, lsb: dict, quality: str, retries: int, force: bool) -> Path:
    """Voz + escena + render de un capítulo. Devuelve su silent.mp4 (reutiliza si nada cambió)."""
    from explapix import llm  # noqa: PLC0415
    d.mkdir(parents=True, exist_ok=True)
    n = len(lsb["chapters"])
    last = k == n - 1
    segs = [dict(s) for s in ch["segments"]]
    if k > 0 and not last:
        segs[0]["chapter"] = ch["title"]
    sb = {"topic": f"{lsb['topic']} · {ch['title']}", "formato": FORMATO, "capitulo": k,
          "capitulo_titulo": ch["title"], "pantalla_final": last, "segments": segs}
    manual = ROOT / "data" / "largos" / lsb["id"] / f"{d.name}.py"
    key = hashlib.sha1(json.dumps([sb, quality, manual.read_text(encoding="utf-8") if manual.exists() else ""],
                                  ensure_ascii=False).encode()).hexdigest()
    done = _read(d / "done.json", {}) or {}
    silent = next((d / "media").rglob("silent.mp4"), None) if (d / "media").exists() else None
    if not force and done.get("key") == key and silent and silent.exists():
        print(f"   capítulo {k} ({ch['title']}): ya estaba hecho", flush=True)
        return silent
    _write(d / "storyboard.json", sb)
    if done.get("narration") != json.dumps(segs, ensure_ascii=False) or not (d / "timing.json").exists() or force:
        print(f"   capítulo {k} ({ch['title']}): voz", flush=True)
        tts.narrate([s["narration"] for s in segs], d / "audio")
        shutil.copy(d / "audio" / "timing.json", d / "timing.json")
    timing = _read(d / "timing.json")
    scene_file = d / "scene.py"
    shutil.rmtree(d / "media", ignore_errors=True)
    print(f"   capítulo {k} ({ch['title']}): animación", flush=True)
    if manual.exists():
        shutil.copy(manual, scene_file)
        ok, log, silent = render.render_scene(scene_file, d, quality, formato=FORMATO)
    else:
        code, err, ok = None, None, False
        extra = (f"Este es el capítulo {k} de {n - 1} del video largo «{lsb['title']}»."
                 + (" Es la INTRO: sin tarjeta de capítulo." if k == 0 else "")
                 + (" Es el CIERRE: termina con la pantalla final." if last else ""))
        for attempt in range(retries + 1):
            code = llm.scene_code(sb, timing, previous=code, error=err, formato=FORMATO, extra=extra)
            scene_file.write_text(code, encoding="utf-8")
            ok, log, silent = render.render_scene(scene_file, d, quality, formato=FORMATO)
            if ok:
                break
            err = log
            shutil.rmtree(d / "media", ignore_errors=True)
            print(f"   intento {attempt + 1} falló, corrigiendo…", flush=True)
    if not ok:
        (d / "render_error.log").write_text(log, encoding="utf-8")
        raise SystemExit(f"Render del capítulo {k} falló, ver {d / 'render_error.log'}")
    _write(d / "done.json", {"key": key, "narration": json.dumps(segs, ensure_ascii=False),
                             "at": datetime.now().isoformat(timespec="seconds")})
    return silent


def assemble(lsb: dict, work: Path, silents: list[Path]) -> dict:
    """Une capítulos (video, voz, efectos, timing, guion) en la carpeta del largo."""
    import numpy as np  # noqa: PLC0415
    from explapix.tts import SR_OUT, _load_trimmed, _write_wav  # noqa: PLC0415,F401
    caps = chapter_dirs(lsb, work)
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in silents), encoding="utf-8")
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(silent)], check=True)
    voice, events, tsegs, segs, chapters, t0 = [], [], [], [], [], 0.0
    for (k, ch, d), sp in zip(caps, silents):
        vdur = render._dur(sp)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(d / "audio" / "narration.wav"), "-ac", "1", "-ar",
                              str(SR_OUT), "-f", "s16le", "-"], capture_output=True, check=True).stdout
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
        n = int(round(vdur * SR_OUT))
        voice.append(np.pad(x, (0, max(0, n - len(x))))[:n])     # la voz dura lo mismo que el video
        for e in _read(d / "sfx_events.json", []) or []:
            events.append({**e, "t": round(e["t"] + t0, 3)})
        tm = _read(d / "timing.json", {}) or {}
        tsegs += tm.get("segments", [])
        segs += (_read(d / "storyboard.json", {}) or {}).get("segments", [])
        chapters.append({"title": ch["title"] if k else (ch.get("title") or "Intro"), "start": round(t0, 2),
                         "short_id": ch.get("short_id"), "dir": d.name})
        t0 += vdur
    (work / "audio").mkdir(exist_ok=True)
    _write_wav(work / "audio" / "narration.wav", np.concatenate(voice))
    _write(work / "sfx_events.json", sorted(events, key=lambda e: e["t"]))
    # en timing.json el último segmento absorbe el resto del capítulo (pantalla final, tarjetas)
    _write(work / "timing.json", {"engine": tts.engine_name(), "segments": tsegs,
                                  "total": round(sum(s["duration"] for s in tsegs), 3)})
    _write(work / "storyboard.json", {k_: v for k_, v in lsb.items() if k_ != "chapters"} | {"segments": segs})
    return {"silent": silent, "chapters": chapters, "duration": t0}


def write_texts(lsb: dict, work: Path) -> dict:
    """Descripción con capítulos y enlaces a los shorts + pausas para anuncios → meta.json."""
    from explapix import qa  # noqa: PLC0415
    meta = _read(work / "meta.json", {}) or {}
    chapters = meta.get("chapters") or []
    total = meta.get("duration") or 0
    r = qa.reglas()
    gap = qa._p(r, "video_largo", "anuncio_cada_min_s", 120)
    endf = qa._p(r, "video_largo", "pantalla_final_s", 20)
    meta.update({"title": lsb["title"], "description": build_description(lsb, chapters), "tags": lsb["tags"],
                 "topic": lsb["topic"], "formato": FORMATO, "largo_id": lsb["id"],
                 "ad_breaks": [_mmss(t) for t in ad_breaks(chapters, total, gap)],
                 "end_screen_from": _mmss(max(total - endf, 0)),
                 "pinned_comment": lsb.get("pinned_comment", ""),
                 "shorts": [c["short_id"] for c in chapters if c.get("short_id")]})
    _write(work / "meta.json", meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard", type=Path, help="data/largos/<id>.json")
    from explapix import config
    ap.add_argument("--quality", choices=list(render.QUALITY), default=config.get("formato.calidad", "hd"))
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--redo", action="append", default=[], help="carpeta de capítulo a rehacer (p. ej. 03-bateria)")
    ap.add_argument("--textos", action="store_true", help="solo rehacer descripción, capítulos y anuncios")
    ap.add_argument("--music", type=Path)
    ap.add_argument("--upload", action="store_true", help="subir a YouTube al terminar (solo si pasa la verificación)")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    a = ap.parse_args()

    lsb = json.loads(a.storyboard.read_text(encoding="utf-8"))
    work = ROOT / "out" / f"largo-{lsb['id']}"
    work.mkdir(parents=True, exist_ok=True)
    if a.textos:
        meta = write_texts(lsb, work)
        print(meta["description"])
        return

    caps = chapter_dirs(lsb, work)
    print(f"[1/4] Capítulos: {len(caps)} ({lsb['title']})", flush=True)
    silents = [build_chapter(k, ch, d, lsb, a.quality, a.retries, d.name in a.redo) for k, ch, d in caps]

    print("[2/4] Unión de capítulos", flush=True)
    asm = assemble(lsb, work, silents)

    print("[3/4] Mezcla final", flush=True)
    from explapix import music as music_lib, qa, sfx  # noqa: PLC0415
    m = a.music or music_lib.pick()
    ev = sfx.load_events(work / "sfx_events.json")
    wav = work / "audio" / "sfx.wav"
    sfx.build_track(ev, asm["duration"], wav)
    final = render.mux(asm["silent"], work / "audio" / "narration.wav", work / "final.mp4", m, wav)
    meta = _read(work / "meta.json", {}) or {}
    meta.update({"file": str(final), "duration": round(asm["duration"], 2), "chapters": asm["chapters"],
                 "quality": a.quality, "music": m.name if m else None, "sfx": bool(ev),
                 "engine": tts.engine_name(), "created": datetime.now().isoformat(timespec="seconds")})
    _write(work / "meta.json", meta)
    meta = write_texts(lsb, work)

    print("[4/4] Verificación", flush=True)
    res = qa.check(work)
    qa.save(work, res)
    bad = [c["id"] for c in res["checks"] if not c["ok"]]
    print(f"   {res['passed']}/{res['total']} " + ("✓" if res["ok"] else "✗ necesita corrección: " + ", ".join(bad)),
          flush=True)
    print(f"   duración {_mmss(asm['duration'])} · anuncios sugeridos en {', '.join(meta['ad_breaks']) or '—'} · "
          f"pantalla final desde {meta['end_screen_from']}", flush=True)
    if a.upload:
        if not res["ok"]:
            raise SystemExit("No subo un video que no pasó la verificación")
        from explapix import youtube  # noqa: PLC0415
        meta = _read(work / "meta.json")
        meta["youtube_id"] = youtube.upload(final, meta["title"], meta["description"], meta["tags"], a.privacy,
                                            short=False)
        meta["privacy"] = a.privacy
        _write(work / "meta.json", meta)
        print(f"   subido: https://youtu.be/{meta['youtube_id']} ({a.privacy})", flush=True)
    print(f"Listo: {final}", flush=True)


if __name__ == "__main__":
    main()
