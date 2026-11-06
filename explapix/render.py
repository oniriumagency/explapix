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
    env = dict(os.environ, EXPLAPIX_TIMING=str((workdir / "timing.json").resolve()))
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


def mux(video: Path, narration: Path, out: Path, music: Path | None = None,
        music_volume: float = 0.12) -> Path:
    """Une video + voz (+ música de fondo opcional con ducking suave)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if music and music.exists():
        fc = (f"[2:a]volume={music_volume},aloop=loop=-1:size=2e9[m];"
              f"[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(narration), "-i", str(music),
               "-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(narration),
               "-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-shortest", "-movflags", "+faststart", str(out)]
    if music and music.exists():  # -af no se puede combinar con filter_complex
        i = cmd.index("-af")
        del cmd[i:i + 2]
    subprocess.run(cmd, check=True)
    return out


def have(binary: str) -> bool:
    return shutil.which(binary) is not None
