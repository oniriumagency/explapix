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
# Voces neuronales (GPU NVIDIA recomendada): Chatterbox (MIT) y Kokoro (Apache-2.0)
[ -d .venv-tts ] || { python3 -m venv .venv-tts && .venv-tts/bin/pip install -q -U pip && .venv-tts/bin/pip install -q -r requirements-tts.txt; }
[ -d .venv-kokoro ] || { python3 -m venv .venv-kokoro && .venv-kokoro/bin/pip install -q -U pip && .venv-kokoro/bin/pip install -q "kokoro>=0.9" soundfile; }
[ -f voices/ref.wav ] || python -m explapix.tts ref
# Motor de animación alternativo (HyperFrames): Node 22+, paquetes fijados y Chrome headless
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs
fi
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
     libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
  && { sudo apt-get install -y libasound2t64 || sudo apt-get install -y libasound2; }
(cd hyperframes && npm ci --no-audit --no-fund && HYPERFRAMES_NO_TELEMETRY=1 node node_modules/hyperframes/bin/hyperframes.mjs browser ensure)
echo "Listo. Prueba sin costo:"
echo "  . .venv/bin/activate && python make_video.py --storyboard examples/refrigerador/storyboard.json --scene examples/refrigerador/scene.py"
