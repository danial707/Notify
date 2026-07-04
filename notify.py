#!/usr/bin/env python3
"""
Notify.exe
----------
Simple CLI Discord notifier for scripts, macros, automations, etc.

Usage:
    Notify.exe <command> [message...]

Commands:
    start        Sends a "started" notification (no screenshot)
    success      Sends a "success" notification (no screenshot)
    error        Sends an "error" notification (no screenshot)
    warning      Sends a "warning" notification (no screenshot)
    info         Sends an info notification (no screenshot)
    infos        Sends an info notification WITH a screenshot attached
    screenshot   Sends only a screenshot (message optional)

Examples:
    Notify.exe start "Starting build script"
    Notify.exe success "Backup finished OK"
    Notify.exe error "Script crashed on step 3"
    Notify.exe infos "Here's the current screen"
    Notify.exe screenshot

Config:
    Reads config.ini from the same folder as the exe/script.
    See config.ini for the fields it needs.
"""

import sys
import os
import io
import json
import configparser
from datetime import datetime, timezone

CONFIG = None


# --------------------------------------------------------------------------
# Path / config helpers
# --------------------------------------------------------------------------

def get_base_dir():
    """Folder the exe (or script) lives in — that's where config.ini and the log live."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

COMMAND_STYLES = {
    "start":      {"emoji": "🚀", "title": "Started",    "color": 0x3498DB},
    "success":    {"emoji": "✅", "title": "Success",    "color": 0x2ECC71},
    "error":      {"emoji": "❌", "title": "Error",      "color": 0xE74C3C},
    "warning":    {"emoji": "⚠️", "title": "Warning",    "color": 0xF1C40F},
    "info":       {"emoji": "ℹ️", "title": "Info",       "color": 0x95A5A6},
    "infos":      {"emoji": "ℹ️", "title": "Info",       "color": 0x95A5A6},
    "screenshot": {"emoji": "📸", "title": "Screenshot", "color": 0x9B59B6},
}


def create_default_config():
    cfg = configparser.ConfigParser()
    cfg["Discord"] = {
        "webhook_url": "",
        "username": "Notify Bot",
        "avatar_url": "",
    }
    cfg["General"] = {
        "pc_name": "My-PC",
        "log_file": "notify_log.txt",
    }
    cfg["Mention"] = {
        "enabled": "false",
        "user_id": "",
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        cfg.write(f)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        create_default_config()
        print(f"config.ini was missing, so a blank one was created at:\n{CONFIG_PATH}")
        print("Open it, paste in your Discord webhook URL, and run the command again.")
        sys.exit(1)

    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")

    webhook_url = cfg.get("Discord", "webhook_url", fallback="").strip()
    username    = cfg.get("Discord", "username", fallback="Notify").strip() or "Notify"
    avatar_url  = cfg.get("Discord", "avatar_url", fallback="").strip()
    pc_name     = cfg.get("General", "pc_name", fallback=os.environ.get("COMPUTERNAME", "Unknown-PC")).strip()
    log_file    = cfg.get("General", "log_file", fallback="notify_log.txt").strip() or "notify_log.txt"

    if not os.path.isabs(log_file):
        log_file = os.path.join(BASE_DIR, log_file)

    if not webhook_url:
        print("webhook_url is empty in config.ini — set it to your Discord webhook URL and try again.")
        sys.exit(1)

    mention_enabled = cfg.getboolean("Mention", "enabled", fallback=False)
    mention_user_id = cfg.get("Mention", "user_id", fallback="").strip()

    if mention_enabled and not mention_user_id:
        print("Mention is enabled in config.ini but user_id is empty — mentions will be skipped.")
        mention_enabled = False

    return {
        "webhook_url": webhook_url,
        "username": username,
        "avatar_url": avatar_url,
        "pc_name": pc_name,
        "log_file": log_file,
        "mention_enabled": mention_enabled,
        "mention_user_id": mention_user_id,
    }


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def log_line(text):
    if not CONFIG:
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CONFIG["log_file"], "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")
    except Exception:
        pass  # never let logging failure crash the notifier


# --------------------------------------------------------------------------
# Screenshot
# --------------------------------------------------------------------------

def take_screenshot():
    try:
        from PIL import ImageGrab
    except ImportError:
        log_line("ERROR: Pillow not installed — can't take screenshot. Run: pip install Pillow")
        return None
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception as e:
        log_line(f"ERROR taking screenshot: {e}")
        return None


# --------------------------------------------------------------------------
# Discord webhook
# --------------------------------------------------------------------------

def send_discord(config, command, message, screenshot_buf=None):
    try:
        import requests
    except ImportError:
        log_line("ERROR: 'requests' not installed. Run: pip install requests")
        print("Missing dependency: requests. Run: pip install requests")
        return

    style = COMMAND_STYLES.get(command, COMMAND_STYLES["info"])
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    embed = {
        "title": f"{style['emoji']} {style['title']} — {config['pc_name']}",
        "description": message if message else "*(no message)*",
        "color": style["color"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"{config['pc_name']} • {now_local}"},
    }

    payload = {"username": config["username"], "embeds": [embed]}
    if config["avatar_url"]:
        payload["avatar_url"] = config["avatar_url"]

    if config.get("mention_enabled") and config.get("mention_user_id"):
        payload["content"] = f"<@{config['mention_user_id']}>"
        # allowed_mentions restricts pings to just this user, so nothing else
        # in the embed/content can accidentally mass-ping the server
        payload["allowed_mentions"] = {"parse": [], "users": [config["mention_user_id"]]}

    try:
        if screenshot_buf:
            embed["image"] = {"url": "attachment://screenshot.png"}
            files = {"file": ("screenshot.png", screenshot_buf, "image/png")}
            data = {"payload_json": json.dumps(payload)}
            resp = requests.post(config["webhook_url"], data=data, files=files, timeout=15)
        else:
            resp = requests.post(config["webhook_url"], json=payload, timeout=15)

        if resp.status_code not in (200, 204):
            log_line(f"{command.upper()} FAILED ({resp.status_code}): {resp.text[:300]} | msg='{message}'")
        else:
            log_line(f"{command.upper()} sent | msg='{message}'")
    except Exception as e:
        log_line(f"ERROR sending to Discord: {e} | msg='{message}'")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    global CONFIG

    args = sys.argv[1:]
    if not args:
        print("Usage: Notify.exe <command> [message...]")
        print("Commands: start, success, error, warning, info, infos, screenshot")
        sys.exit(1)

    command = args[0].lstrip("-").lower()
    message = " ".join(args[1:]) if len(args) > 1 else ""

    if command not in COMMAND_STYLES:
        print(f"Unknown command: {command}")
        print("Valid commands: start, success, error, warning, info, infos, screenshot")
        sys.exit(1)

    CONFIG = load_config()

    screenshot_buf = None
    if command in ("infos", "screenshot"):
        screenshot_buf = take_screenshot()

    send_discord(CONFIG, command, message, screenshot_buf)
    # exit immediately, no hanging window / no waiting on user input


if __name__ == "__main__":
    main()
