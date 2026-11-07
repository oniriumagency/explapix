"""Render con Manim + mezcla final con ffmpeg."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

QUALITY = {  # (ancho, alto, fps) en vertical
    "draft": (540, 960, 24),
    "hd": (1080, 1920, 30),
}


def render_scene(scene_file: Path, workdir: Path, quality: str = "hd",
                 scene_name: str = "Video") -> tuple[bool, str, Path | None]:
    w, h, fps = QUALITY[quality]
    env = dict(os.environ, EXPLAPIX_TIMING=str((workdir / "timing.json").resolve()),
               EXPLAPIX_SFX_EVENTS=str((workdir / "sfx_events.json").resolve()),
               EXPLAPIX_STORYBOARD=str((workdir / "storyboard.json").resolve()))
    root = Path(__file__).resolve().parent.parent
    env["PYTHONPATH"] = f"{root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    media = workdir / "media"
    cmd = [sys.executable, "-m", "manim", "render", str(scene_file), scene_name,
           "-r", f"{w},{h}", "--fps", str(fps), "--media_dir", str(media),
           "--disable_caching", "--progress_bar", "none", "-o", "silent.mp4"]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    log = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        return False, log[-6000:], None
    out = next(media.rglob("silent.mp4"), None)
    return out is not None, log[-2000:], out


def _dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(p)], capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def mux(video: Path, narration: Path, out: Path, music: Path | None = None,
        sfx_track: Path | None = None, music_db: float | None = None, sfx_db: float | None = None) -> Path:
    """Video + voz + música (fade in/out, ducking bajo la voz) + efectos (ducking suave).

    La voz se normaliza a -16 LUFS; la música queda ~20 dB por debajo y baja otros ~8 dB cuando
    hay voz (sidechain); los efectos ~14 dB por debajo de la voz.
    """
    from explapix import config  # noqa: PLC0415
    music_db = float(config.get("audio.musica_db", -21) if music_db is None else music_db)
    sfx_db = float(config.get("audio.efectos_db", -13) if sfx_db is None else sfx_db)
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = _dur(video)
    inputs = ["-i", str(video), "-i", str(narration)]
    fc = [f"[1:a]aresample=48000,aformat=channel_layouts=mono,loudnorm=I=-16:TP=-2:LRA=11,"
          f"apad,atrim=0:{dur:.3f},asplit=3[voice][k1][k2]"]
    mix = ["[voice]"]
    n = 2
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fo = max(dur - 2.5, 0)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,loudnorm=I=-16:TP=-2,"
                  f"volume={music_db}dB,atrim=0:{dur:.3f},afade=t=in:d=1.5,afade=t=out:st={fo:.3f}:d=2.5[m0];"
                  f"[m0][k1]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=400:makeup=1[mus]")
        mix.append("[mus]")
        n += 1
    else:
        fc.append("[k1]anullsink")
    if sfx_track and sfx_track.exists():
        inputs += ["-i", str(sfx_track)]
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,volume={sfx_db}dB,"
                  f"apad,atrim=0:{dur:.3f}[s0];[s0][k2]sidechaincompress=threshold=0.05:ratio=2.5:"
                  f"attack=10:release=200:makeup=1[sfx]")
        mix.append("[sfx]")
        n += 1
    else:
        fc.append("[k2]anullsink")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
              "alimiter=limit=0.89,aformat=channel_layouts=stereo[a]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out


def have(binary: str) -> bool:
    return shutil.which(binary) is not None
