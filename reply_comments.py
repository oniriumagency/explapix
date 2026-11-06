#!/usr/bin/env python3
"""Responde comentarios de YouTube e Instagram con Claude.

Modo por defecto (seguro): genera borradores en out/comment_drafts.json para revisarlos.
  python reply_comments.py                 # crea/actualiza borradores
  python reply_comments.py --send-approved # publica los borradores con "approved": true
  python reply_comments.py --auto          # responde directo sin revisión (cuando confíes)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from explapix import instagram, llm, youtube

DRAFTS = Path(__file__).resolve().parent / "out" / "comment_drafts.json"


def load() -> list[dict]:
    return json.loads(DRAFTS.read_text(encoding="utf-8")) if DRAFTS.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--send-approved", action="store_true")
    ap.add_argument("--max", type=int, default=50)
    a = ap.parse_args()

    drafts = load()
    if a.send_approved:
        for d in drafts:
            if d.get("approved") and not d.get("sent") and not d.get("discarded"):
                plat = instagram if d.get("platform") == "instagram" else youtube
                d["reply_id"] = plat.reply(d["comment_id"], d["reply"])
                d["sent"] = True
                print(f"✓ {d['author']}: {d['reply']}")
        youtube.save_json(DRAFTS, drafts)
        return

    known = {d["comment_id"] for d in drafts}
    videos: dict[str, dict] = {}
    found = []
    if youtube.TOKEN.exists():
        found += [{**c, "platform": "youtube"} for c in youtube.unanswered_comments(a.max)]
    if instagram.connected():
        found += instagram.unanswered_comments()
    for c in found:
        if c["comment_id"] in known:
            continue
        if c["platform"] == "instagram":
            v = {"title": c.pop("video_title", ""), "description": c.pop("video_description", "")}
        else:
            v = videos.setdefault(c["video_id"], youtube.video_info(c["video_id"]))
        r = llm.reply_to_comment(v["title"], v["description"], c["text"])
        d = {**c, **r, "approved": False, "sent": False}
        if a.auto and not r["skip"]:
            d["reply_id"] = (instagram if c["platform"] == "instagram" else youtube).reply(
                c["comment_id"], r["reply"])
            d["approved"] = d["sent"] = True
        drafts.append(d)
        print(("SKIP " if r["skip"] else "") + f"{c['author']}: {c['text'][:60]} -> {r['reply']}")
    youtube.save_json(DRAFTS, drafts)


if __name__ == "__main__":
    main()
