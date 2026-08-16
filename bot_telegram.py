import asyncio
import os
import re
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "GANTI_DENGAN_TOKEN_BOTFATHER")
AGY_PATH = "/root/.local/bin/agy"
LOG_FILE = "/root/telegram_bot_history.log"

# Hanya chat ID ini yang dijawab (kosongkan list = terbuka semua)
ALLOWED_CHAT_IDS = [int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "904411212").split(",") if x.strip()]

# Persona: biar balasan terasa seperti chat orang yang sadar identitasnya
SYSTEM_STYLE = (
    "Kamu adalah Kezem yang chat via Telegram dengan Golem — Golem adalah orang "
    "yang memberi namamu. Kamu SELALU tahu dirimu Kezem. Jika Golem menyapa "
    "('halo', 'hai'), balas hangat dan perkenalkan dirimu sebagai Kezem dengan "
    "variasi yang natural, contoh: 'Halo Golem! Kezem di sini, ada apa?' — "
    "tapi untuk pertanyaan biasa JANGAN buka dengan sapaan, langsung jawab "
    "isinya. Untuk soal matematika/analisis: pikirkan teliti langkah demi "
    "langkah sebelum menjawab, jangan asal cepat. Gaya santai Indonesia, tanpa "
    "heading markdown atau simbol **bold**/`code`, jangan tanda tangan '- kezem'."
)


def clean_reply(text):
    """Bersihkan markdown mentah supaya enak dibaca di Telegram."""
    if not text:
        return text
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
    text = text.replace("```", "")
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def log_to_file(role, text):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {role}:\n{text}\n{'-'*40}\n")
    except Exception as e:
        print(f"Gagal menulis ke log: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo Golem! Kezem di sini 🤖\n"
        "Otak: Gemini 3.1 Pro (High) via Antigravity\n\n"
        "Perintah:\n"
        "/new - reset konteks chat\n"
        "Kirim teks atau foto — semua bisa dibaca."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Kezem siap bantu: tanya apa saja, kirim foto/gambar, "
        "soal matematika, coding, analisis.\n"
        "/new buat mulai konteks baru."
    )

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset konteks: hapus memori percakapan user ini."""
    user_id = update.effective_user.id
    conv_id = f"tg_bot_{user_id}"
    # Buat percakapan baru dengan suffix timestamp agar mulai fresh
    import time as _t
    new_conv = f"{conv_id}_{int(_t.time())}"
    context.bot_data[f"conv_{user_id}"] = new_conv
    await update.message.reply_text("🔄 Konteks direset. Chat berikutnya mulai baru.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Whitelist: abaikan chat yang tidak dikenal
    if ALLOWED_CHAT_IDS and update.effective_chat.id not in ALLOWED_CHAT_IDS:
        return

    user_text = update.message.text or update.message.caption or ""
    file_info_text = ""
    
    # Memicu status "Mengetik..." asli dari Telegram di bawah nama bot
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_path = f"/root/tg_image_{photo.file_id}.jpg"
            await file.download_to_drive(file_path)
            file_info_text = f"\n\n[Sistem Instruksi: Pengguna melampirkan gambar di {file_path}.]"
            
        full_prompt = (user_text + file_info_text).strip()
        if not user_text and file_info_text:
            full_prompt = "Tolong jelaskan gambar yang baru saja saya lampirkan ini." + file_info_text
            
        log_to_file("USER", full_prompt)
        
        try:
            with open("/root/memory.md", "r", encoding="utf-8") as f:
                mem_context = f.read().strip()
            final_prompt = f"[System Memory:\n{mem_context}]\n\nUser: {full_prompt}"
        except:
            final_prompt = full_prompt

        user_id = update.effective_user.id
        # Pakai percakapan aktif (bisa di-reset via /new); fallback default
        conv_id = context.bot_data.get(f"conv_{user_id}", f"tg_bot_{user_id}")

        # Tambahkan instruksi gaya chat natural di awal prompt
        styled_prompt = f"[Instruksi gaya: {SYSTEM_STYLE}]\n\n{final_prompt}"

        process = await asyncio.create_subprocess_exec(
            AGY_PATH, "--conversation", conv_id, "-p", styled_prompt,
            "--effort", "high",
            "--dangerously-skip-permissions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/root"
        )
        
        output_msg = ""
        last_edit_time = time.time()
        last_typing_time = time.time()
        status_msg = None  # pesan dibuat hanya setelah ada output pertama
        import codecs
        decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')
        
        while True:
            chunk = await process.stdout.read(1024)
            if not chunk:
                output_msg += decoder.decode(b'', final=True)
                break
                
            output_msg += decoder.decode(chunk)
            current_time = time.time()
            
            # Refresh status "typing..." asli Telegram setiap 4 detik
            if current_time - last_typing_time > 4.0:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                last_typing_time = current_time
            
            # Streaming: kirim pesan pertama begitu ada output, lalu edit
            if current_time - last_edit_time > 1.5:
                if output_msg.strip():
                    display_text = clean_reply(output_msg.strip())
                    if len(display_text) > 4000:
                        display_text = display_text[-4000:]
                    try:
                        if status_msg is None:
                            status_msg = await update.message.reply_text(display_text)
                        else:
                            await status_msg.edit_text(display_text)
                    except Exception:
                        pass
                last_edit_time = current_time
                
        await process.wait()
        err_reply = (await process.stderr.read()).decode('utf-8', errors='ignore').strip()
        
        if err_reply and process.returncode != 0:
            output_msg += f"\n\n[Diagnostic Logs / Error]:\n{err_reply}"
            
        log_to_file("BOT_OUTPUT", output_msg)
            
        if output_msg.strip():
            display_text = clean_reply(output_msg.strip())
            if len(display_text) > 4000:
                display_text = display_text[-4000:]
            try:
                if status_msg is None:
                    await update.message.reply_text(display_text)
                else:
                    await status_msg.edit_text(display_text)
            except:
                pass

    except Exception as e:
        error_msg = f"Terjadi exception Python: {e}"
        try:
            await update.message.reply_text(error_msg)
        except Exception:
            pass
        log_to_file("FATAL_ERROR", error_msg)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("new", reset_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    print("Bot Telegram siap berjalan (Native Typing Aktif + Markdown Cleaner + Whitelist)...")
    app.run_polling()

if __name__ == "__main__":
    main()
