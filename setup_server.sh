#!/usr/bin/env bash
# Instalación en Magne Server (Ubuntu/Debian). Uso: bash setup_server.sh
set -euo pipefail
cd "$(dirname "$0")"
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev build-essential pkg-config ffmpeg \
     libcairo2-dev libpango1.0-dev fonts-dejavu espeak-ng
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
mkdir -p voices secrets out && chmod 700 secrets
# Voz en español (Piper). Alternativas: es_ES-davefx-medium, es_MX-ald-medium
V=es/es_MX/claude/high/es_MX-claude-high
for ext in onnx onnx.json; do
  [ -f "voices/$(basename $V).$ext" ] || curl -sSL -o "voices/$(basename $V).$ext" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/$V.$ext"
done
echo "Listo. Prueba sin costo:"
echo "  . .venv/bin/activate && python make_video.py --storyboard examples/refrigerador/storyboard.json --scene examples/refrigerador/scene.py"
