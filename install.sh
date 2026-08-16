# ============================================================
# Kezem Telegram Bot - Installer untuk VPS baru (Ubuntu/Debian)
# Bot Telegram <-> Antigravity CLI (agy / Gemini 3.1 Pro)
# ============================================================
# CARA PAKAI:
#   1. Pastikan Antigravity CLI (agy) sudah terinstall & login: agy models
#   2. Set token bot:
#        export BOT_TOKEN="token_dari_botfather"
#        export ALLOWED_CHAT_IDS="chat_id_kamu"
#   3. Jalankan: bash install.sh
# ============================================================
set -e

BOT_TOKEN="${BOT_TOKEN:-GANTI_DENGAN_TOKEN_BOTFATHER}"
ALLOWED_CHAT_IDS="${ALLOWED_CHAT_IDS:-904411212}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$BOT_TOKEN" = "GANTI_DENGAN_TOKEN_BOTFATHER" ]; then
    echo "!! BOT_TOKEN belum diset."
    echo "   export BOT_TOKEN=\"token_dari_botfather\" lalu jalankan lagi."
    exit 1
fi

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

echo "=== [4/5] Pasang systemd service (dengan token kamu) ==="
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
Environment=BOT_TOKEN=$BOT_TOKEN
Environment=ALLOWED_CHAT_IDS=$ALLOWED_CHAT_IDS

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable gemini-telegram-bot

echo "=== [5/5] Cek prasyarat agy ==="
if command -v agy >/dev/null 2>&1 || [ -x /root/.local/bin/agy ]; then
    echo "agy ditemukan."
    /root/.local/bin/agy models >/dev/null 2>&1 && echo "  -> OK, agy siap" || echo "  -> PERLU LOGIN: jalankan 'agy' sekali untuk auth OAuth"
else
    echo "!! agy TIDAK ditemukan. Install Antigravity CLI dulu dan login."
fi

echo
echo "=== SELESAI ==="
echo "Start bot:   systemctl start gemini-telegram-bot"
echo "Cek status:  systemctl status gemini-telegram-bot"
echo "Lihat log:   journalctl -u gemini-telegram-bot -f"
