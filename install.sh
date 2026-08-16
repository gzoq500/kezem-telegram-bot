#!/usr/bin/env bash
# ============================================================
# Kezem Telegram Bot - Installer untuk VPS baru (Ubuntu/Debian)
# Bot Telegram <-> Antigravity CLI (agy / Gemini 3.1 Pro)
# ============================================================
# CARA PAKAI:
#   1. Pastikan Antigravity CLI (agy) sudah login: agy auth login
#   2. Edit BOT_TOKEN di bawah (atau biarkan, sudah terisi)
#   3. Jalankan: bash install.sh
# ============================================================
set -e

BOT_TOKEN="8810619082:AAEAqdW-q0w4y7QgQvSuaMJBpPJ6SYp3mdY"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== [1/5] Install dependensi Python ==="
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip

echo "=== [2/5] Buat virtualenv ==="
python3 -m venv /root/venv
/root/venv/bin/pip install --quiet --upgrade pip
/root/venv/bin/pip install --quiet "python-telegram-bot[job-queue]"

echo "=== [3/5] Pasang file bot ==="
cp "$SCRIPT_DIR/bot_telegram.py" /root/bot_telegram.py
cp "$SCRIPT_DIR/memory.md" /root/memory.md

echo "=== [4/5] Pasang systemd service ==="
cat > /etc/systemd/system/gemini-telegram-bot.service <<EOF
[Unit]
Description=Gemini Telegram Bot (agy + python-telegram-bot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/root/venv/bin/python /root/bot_telegram.py
WorkingDirectory=/root
Restart=always
RestartSec=5
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=HOME=/root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable gemini-telegram-bot

echo "=== [5/5] Cek prasyarat agy ==="
if command -v agy >/dev/null 2>&1 || [ -x /root/.local/bin/agy ]; then
    echo "agy ditemukan. Login status:"
    /root/.local/bin/agy models >/dev/null 2>&1 && echo "  -> OK, agy siap" || echo "  -> PERLU LOGIN: jalankan 'agy' sekali untuk auth OAuth"
else
    echo "!! agy TIDAK ditemukan. Install Antigravity CLI dulu dan login:"
    echo "   Lihat: https://antigravity.google / dokumentasi Antigravity CLI"
fi

echo
echo "=== SELESAI ==="
echo "Start bot:   systemctl start gemini-telegram-bot"
echo "Cek status:  systemctl status gemini-telegram-bot"
echo "Lihat log:   journalctl -u gemini-telegram-bot -f"
