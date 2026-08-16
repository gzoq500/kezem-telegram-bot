#!/usr/bin/env python3
"""
Telegram <-> Antigravity CLI (agy) Bridge Daemon
=================================================
Polls Telegram for incoming messages, forwards them to `agy -p`
(Gemini 3.1 Pro), and sends the reply back to Telegram.

Runs 24/7. Context is kept across messages via `agy --continue`.

Usage:
    python3 bridge.py            # run foreground
    python3 bridge.py --once     # process a single update then exit (test)

Config: config.json next to this file.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
LOG_PATH = os.path.join(HERE, "bridge.log")

DEFAULT_CONFIG = {
    "bot_token": "PASTE_YOUR_BOT_TOKEN_HERE",
    "allowed_chat_ids": [],          # empty = allow everyone (not recommended)
    "agy_bin": "/root/.local/bin/agy",
    "model": "gemini-3.1-pro-high",  # see `agy models`
    "keep_context": True,            # use --continue so it remembers the chat
    "max_reply_chars": 4000,         # Telegram hard limit 4096
    "agy_timeout": 300,              # seconds to wait for agy
    "poll_timeout": 60,              # long-poll seconds
    "system_prefix": "",             # optional instruction prepended to every msg
}


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    else:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    return cfg


def tg_api(token, method, params=None, timeout=90):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "description": str(e)}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def clean_reply(text):
    """Convert agy markdown output into clean Telegram-friendly text.

    Strategy: convert **bold** and *italic* to plain words, collapse
    fenced code blocks (keep content, drop the fences), and strip
    heading markers so the message reads naturally in Telegram.
    """
    if not text:
        return text
    # Remove fenced code blocks but keep their content indented
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
    text = text.replace("```", "")
    # Inline code -> keep content without backticks
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    # Bold
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    # Italic
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    # Headings
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # List bullets: normalize
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Strip link syntax [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", text)
    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def send_message(token, chat_id, text):
    """Send text, splitting into chunks under the Telegram limit."""
    text = clean_reply(text) or "(empty reply)"
    # Telegram markdown safety: send as plain text to avoid parse errors
    for i in range(0, min(len(text), 30000), 4000):
        chunk = text[i:i + 4000]
        tg_api(token, "sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
        })


def run_agy(cfg, user_text, first_message):
    """Run agy in print mode. Keeps context with --continue when enabled."""
    prompt = user_text.strip()
    if cfg.get("system_prefix"):
        prompt = f"{cfg['system_prefix']}\n\n{prompt}"

    cmd = [cfg["agy_bin"], "-p", prompt,
           "--model", cfg["model"],
           "--output-format", "text"]
    if cfg.get("keep_context") and not first_message:
        cmd.insert(1, "--continue")

    log(f"agy cmd: {' '.join(shlex.quote(c) for c in cmd[:4])}... "
        f"(prompt {len(prompt)} chars)")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=cfg["agy_timeout"],
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if out:
            return out
        if err:
            return f"⚠️ agy error:\n{err[:1500]}"
        return "(agy returned nothing)"
    except subprocess.TimeoutExpired:
        return f"⏱️ Timeout: agy took more than {cfg['agy_timeout']}s."
    except FileNotFoundError:
        return f"❌ agy binary not found at {cfg['agy_bin']}"
    except Exception as e:
        return f"❌ Bridge error: {e}"


def strip_command_entities(text):
    return re.sub(r"/start|/help|/reset|/new", "", text or "").strip()


def main():
    cfg = load_config()
    token = cfg["bot_token"]
    if "PASTE" in token or not token:
        log("❌ Bot token not configured. Edit config.json first.")
        sys.exit(1)

    once = "--once" in sys.argv

    # Validate token
    me = tg_api(token, "getMe", timeout=15)
    if not me.get("ok"):
        log(f"❌ Telegram rejected token: {me.get('description')}")
        sys.exit(1)
    bot_name = me["result"].get("username", "?")
    log(f"✅ Connected as @{bot_name}. Model: {cfg['model']}. "
        f"Context: {'on' if cfg.get('keep_context') else 'off'}. Polling...")

    # Send startup notice to allowed chats
    allowed = cfg.get("allowed_chat_ids") or []
    for cid in allowed:
        tg_api(token, "sendMessage", {
            "chat_id": cid,
            "text": f"🟢 Bridge online — @{bot_name} "
                    f"(model: {cfg['model']})",
        })

    offset = 0
    first_message = True
    while True:
        res = tg_api(token, "getUpdates", {
            "offset": offset,
            "timeout": cfg["poll_timeout"],
        }, timeout=cfg["poll_timeout"] + 30)

        if not res.get("ok"):
            log(f"getUpdates failed: {res.get('description')} — retry in 5s")
            time.sleep(5)
            continue

        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = msg["chat"]["id"]
            text = msg.get("text") or ""

            if allowed and chat_id not in allowed:
                log(f"Ignoring message from unauthorized chat {chat_id}")
                continue

            # Commands
            if text.strip() in ("/new", "/reset"):
                first_message = True
                send_message(token, chat_id,
                             "🔄 Context reset. Next message starts fresh.")
                continue
            if text.strip() == "/start":
                send_message(token, chat_id,
                             "👋 Hi! I'm powered by Gemini via Antigravity "
                             "CLI. Send any message. /new resets context.")
                continue

            text = strip_command_entities(text)
            if not text:
                continue

            log(f"Chat {chat_id}: {text[:80]}{'...' if len(text) > 80 else ''}")
            send_message(token, chat_id, "💭 Thinking...")
            reply = run_agy(cfg, text, first_message)
            first_message = False
            send_message(token, chat_id, reply)
            log(f"Replied to {chat_id}: {len(reply)} chars")

        if once:
            break

    log("Bridge stopped.")


if __name__ == "__main__":
    main()
