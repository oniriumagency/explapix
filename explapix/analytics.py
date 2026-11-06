"""Métricas por video para retroalimentar la elección de temas.

YouTube: Data API (vistas, likes, comentarios: 1 unidad por cada 50 videos) + YouTube Analytics API
(duración media vista y % medio visto; requiere habilitar "YouTube Analytics API" en Google Cloud y
el permiso yt-analytics.readonly, que se pide al conectar YouTube).
Instagram: insights del Reel (alcance, reproducciones, guardados, compartidos, likes, comentarios).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from explapix import instagram, youtube


def youtube_stats(ids: list[str]) -> dict[str, dict]:
    if not ids or not youtube.TOKEN.exists():
        return {}
    from googleapiclient.discovery import build  # noqa: PLC0415
    out: dict[str, dict] = {}
    yt = youtube.service()
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        youtube.spend(1)
        for it in r.get("items", []):
            s = it["statistics"]
            out[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                             "comments": int(s.get("commentCount", 0))}
    try:
        ya = build("youtubeAnalytics", "v2", credentials=youtube.credentials())
        r = ya.reports().query(ids="channel==MINE", startDate="2020-01-01", endDate=date.today().isoformat(),
                               metrics="views,averageViewDuration,averageViewPercentage,shares,subscribersGained",
                               dimensions="video", filters="video==" + ",".join(ids[:200])).execute()
        cols = [c["name"] for c in r.get("columnHeaders", [])]
        for row in r.get("rows", []):
            d = dict(zip(cols, row))
            out.setdefault(d["video"], {}).update(
                avg_view_s=round(d.get("averageViewDuration", 0), 1),
                avg_view_pct=round(d.get("averageViewPercentage", 0), 1),
                shares=d.get("shares", 0), subs=d.get("subscribersGained", 0))
    except Exception as e:  # noqa: BLE001  (API sin habilitar o sin permiso)
        print(f"   YouTube Analytics no disponible: {str(e)[:200]}", flush=True)
    return out


def update_all(out_dir: Path) -> int:
    metas = []
    for d in sorted(out_dir.iterdir()):
        mf = d / "meta.json"
        if mf.exists():
            m = json.loads(mf.read_text(encoding="utf-8"))
            if m.get("youtube_id") or m.get("instagram_id"):
                metas.append((mf, m))
    yt = youtube_stats([m["youtube_id"] for _, m in metas if m.get("youtube_id")])
    n = 0
    for mf, m in metas:
        st = m.get("stats", {})
        if m.get("youtube_id") in yt:
            st["youtube"] = yt[m["youtube_id"]]
        if m.get("instagram_id") and instagram.connected():
            try:
                st["instagram"] = instagram.media_insights(m["instagram_id"])
            except Exception as e:  # noqa: BLE001
                print(f"   Instagram {m['instagram_id']}: {str(e)[:150]}", flush=True)
        st["updated"] = datetime.now().isoformat(timespec="seconds")
        m["stats"] = st
        youtube.save_json(mf, m)
        n += 1
    return n
