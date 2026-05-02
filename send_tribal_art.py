#!/usr/bin/env python3
"""
Tribal Art News — Telegram sender
Sends at most 1 unseen news item per day.
Persists seen state in data/state.json and pushes back to git.
"""
import hashlib, json, os, subprocess, sys, urllib.request, urllib.parse
from datetime import date

BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GIT_PUSH     = os.environ.get("GIT_PUSH", "false").lower() == "true"

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT     = os.path.join(ROOT, "informe_tribal.txt")
STATE_FILE = os.path.join(ROOT, "data", "state.json")

CATEGORY_EMOJI = {
    "subasta":     "🔨",
    "galería":     "🏛️",
    "galeria":     "🏛️",
    "feria":       "🎪",
    "exposición":  "🖼️",
    "exposicion":  "🖼️",
    "restitución": "⚖️",
    "restitucion": "⚖️",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": [], "last_sent_date": ""}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def git_commit_push():
    rel = os.path.relpath(STATE_FILE, ROOT)
    original_url = ""
    if GITHUB_TOKEN:
        result = subprocess.run(
            ["git", "-C", ROOT, "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        original_url = result.stdout.strip()
        auth_url = original_url.replace("https://", f"https://{GITHUB_TOKEN}@")
        subprocess.run(["git", "-C", ROOT, "remote", "set-url", "origin", auth_url], check=False)

    subprocess.run(["git", "-C", ROOT, "add", rel], check=False)
    subprocess.run(
        ["git", "-C", ROOT, "commit", "-m", "chore: update seen state [skip ci]"],
        check=False,
    )
    subprocess.run(["git", "-C", ROOT, "push"], check=False)

    if GITHUB_TOKEN and original_url:
        subprocess.run(["git", "-C", ROOT, "remote", "set-url", "origin", original_url], check=False)


def item_id(title):
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:10]


def shorten_url(url):
    if not url:
        return url
    try:
        api = "https://tinyurl.com/api-create.php?" + urllib.parse.urlencode({"url": url})
        with urllib.request.urlopen(api, timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return url


def parse_items(text):
    items = []
    for block in text.split("===ITEM==="):
        block = block.strip()
        if "===FIN===" not in block:
            continue
        block = block.split("===FIN===")[0].strip()
        item = {}
        for line in block.splitlines():
            if ":" in line:
                k, _, _ = line.partition(":")
                item[k.strip().upper()] = line.split(":", 1)[1].strip()
        if "TITULO" in item:
            items.append(item)
    return items


def format_item(item):
    cat       = item.get("CATEGORIA", "").lower()
    emoji     = CATEGORY_EMOJI.get(cat, "📌")
    cat_label = item.get("CATEGORIA", "").upper()
    url       = shorten_url(item.get("URL", "").strip())

    lines = [
        f"{emoji} <b>{cat_label}</b>",
        "",
        f"<b>{_esc(item.get('TITULO', ''))}</b>",
        "",
        _esc(item.get("RESUMEN", "")),
        "",
        f"📅 {_esc(item.get('FECHA', ''))}  |  {_esc(item.get('FUENTE', ''))}",
    ]
    if url:
        lines.append(f"🔗 {url}")
    return "\n".join(lines)


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def telegram_send(text):
    url  = f"https://api.telegram.org/{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"))


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required.")
        sys.exit(1)

    if not os.path.exists(REPORT):
        print("No report file found.")
        sys.exit(0)

    with open(REPORT, encoding="utf-8") as f:
        content = f.read().strip()

    if "SIN_NOVEDADES" in content:
        print("No news today.")
        sys.exit(0)

    items = parse_items(content)
    if not items:
        print("No valid items found in report.")
        sys.exit(0)

    state = load_state()
    today = str(date.today())

    if state.get("last_sent_date") == today:
        print(f"Already sent one item today ({today}). Nothing to do.")
        sys.exit(0)

    seen = set(state.get("seen", []))
    new_items = [i for i in items if item_id(i["TITULO"]) not in seen]

    if not new_items:
        print("All news items have already been sent.")
        sys.exit(0)

    item = new_items[0]
    telegram_send(format_item(item))

    state["seen"].append(item_id(item["TITULO"]))
    state["last_sent_date"] = today
    save_state(state)

    if GIT_PUSH:
        git_commit_push()

    remaining = len(new_items) - 1
    print(f"Sent: {item['TITULO']}")
    if remaining:
        print(f"{remaining} more item(s) queued for upcoming days.")


if __name__ == "__main__":
    main()
