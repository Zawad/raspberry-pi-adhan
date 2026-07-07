#!/usr/bin/env bash
# Install adhand on a Raspberry Pi. Run from the repo root: ./deploy/install.sh
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_DIR="$(pwd)"

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y vlc-bin vlc-plugin-base mpv alsa-utils bluez python3-venv

echo "==> Creating virtualenv"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Migrating legacy .settings (if present)"
.venv/bin/python scripts/migrate_settings.py || true

echo "==> Installing systemd service"
sed "s|/home/pi/raspberry-pi-adhan|$REPO_DIR|g; s|User=pi|User=$USER|" deploy/adhand.service | sudo tee /etc/systemd/system/adhand.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now adhand

echo "==> Removing legacy cron jobs (rpiAdhanClockJob)"
crontab -l 2>/dev/null | grep -v rpiAdhanClockJob | crontab - || true

echo
echo "Done. Open http://$(hostname).local:8000 from any phone on your Wi-Fi."
echo "Logs: journalctl -u adhand -f"
