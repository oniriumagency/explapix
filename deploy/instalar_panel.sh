#!/usr/bin/env bash
# Instala Explapix Studio como servicio de usuario (arranca solo tras reinicio; linger ya activo).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p ~/.config/systemd/user
cp deploy/explapix-studio.service ~/.config/systemd/user/
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user daemon-reload
systemctl --user enable --now explapix-studio.service
sleep 2
systemctl --user --no-pager status explapix-studio.service | head -5
echo "Panel: http://100.96.241.48:8097  usuario: magne  contraseña: $(cat secrets/panel_password 2>/dev/null || echo '(se crea al primer arranque, vuelve a correr este script)')"
