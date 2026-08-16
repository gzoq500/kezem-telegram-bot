# Kezem Telegram Bot 🤖

Bot Telegram 24/7 bertenaga **Gemini 3.1 Pro (High)** via Antigravity CLI (`agy`).
Punya identitas "Kezem", kenal pemiliknya "Golem", bisa baca foto/gambar,
balasan streaming ala chat manusia, dan markdown otomatis dibersihkan.

## Komponen

| File | Fungsi |
|---|---|
| `bot_telegram.py` | Bot utama (python-telegram-bot + agy) |
| `memory.md` | Memori identitas & aturan perilaku |
| `install.sh` | Installer 1-klik untuk VPS baru |
| `telegram-agy-bridge/` | Versi alternatif bridge sederhana (tidak dipakai aktif) |

## Fitur

- ✅ Typing indicator asli Telegram + streaming reply (edit tiap 1.5s)
- ✅ Identitas: sadar diri "Kezem", memanggil user "Golem"
- ✅ Vision: baca foto/gambar yang dikirim user
- ✅ Reasoning effort HIGH (pikir teliti sebelum jawab)
- ✅ Konteks percakapan persisten (`agy --conversation`)
- ✅ Markdown cleaner (tanpa simbol `**` / `##` mentah)
- ✅ Whitelist chat ID (hanya pemilik yang dijawab)
- ✅ Systemd 24/7: auto-restart + auto-boot
- ✅ Perintah: `/start`, `/help`, `/new` (reset konteks)

## Instalasi di VPS Baru

### Prasyarat
1. VPS Ubuntu/Debian dengan akses root
2. **Antigravity CLI (`agy`) sudah terinstall & sudah login OAuth** (penting!)
3. Bot token Telegram (dari @BotFather)

### Langkah

```bash
# 1. Clone repo ini
git clone https://github.com/gzoq500/kezem-telegram-bot.git
cd kezem-telegram-bot

# 2. (Jika agy belum ada) install Antigravity CLI dan login:
#    - Download/install Antigravity CLI
#    - Jalankan `agy` sekali, login dengan akun Google
agy models   # verifikasi login berhasil (harus list model)

# 3. Jalankan installer
bash install.sh

# 4. Start bot
systemctl start gemini-telegram-bot

# 5. Cek jalan
systemctl status gemini-telegram-bot
journalctl -u gemini-telegram-bot -f
```

### Konfigurasi

Edit `/root/bot_telegram.py` bagian atas:

```python
TELEGRAM_BOT_TOKEN = "..."      # token dari @BotFather
ALLOWED_CHAT_IDS = [904411212]  # chat ID kamu (kosongkan [] = terbuka semua)
```

Ganti model di argument `agy` (default `--effort high`):
opsi: `gemini-3.1-pro-high`, `gemini-3.7-flash-high`,
`claude-sonnet-4-6`, `claude-opus-4-6-thinking`, dll — cek `agy models`.

Edit `/root/memory.md` untuk mengubah identitas/aturan perilaku.

## Perintah Bot

| Perintah | Fungsi |
|---|---|
| `/start` | Perkenalan + info |
| `/help` | Bantuan singkat |
| `/new` atau `/reset` | Reset konteks percakapan |

## Maintenance

```bash
systemctl restart gemini-telegram-bot   # restart
systemctl stop gemini-telegram-bot      # stop
tail -f /root/telegram_bot_history.log  # riwayat chat
journalctl -u gemini-telegram-bot -f    # log live
```

## Arsitektur

```
Telegram ──> bot_telegram.py (polling, systemd 24/7)
              ├── typing indicator + streaming edit
              ├── download foto ──> path lokal
              └── agy --conversation <id> -p "<prompt>" --effort high
                    └── Gemini 3.1 Pro ──> balasan ──> Telegram
```
