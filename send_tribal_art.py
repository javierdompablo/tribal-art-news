#!/usr/bin/env python3
import hashlib, os, sys, urllib.request, urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
REPORT    = os.path.join(os.path.dirname(__file__), "informe_tribal.txt")
SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_tribal_news.txt")

CATEGORY_EMOJI = {
    "subasta":"🔨","galería":"🏛️","galeria":"🏛️","feria":"🎪",
    "exposición":"🖼️","exposicion":"🖼️","restitución":"⚖️","restitucion":"⚖️",
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(seen)) + "\n")

def item_id(title):
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:10]

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
                key, _, val = line.partition(":")
                item[key.strip().upper()] = val.strip()
        if "TITULO" in item:
            items.append(item)
    return items

def format_item(item):
    cat = item.get("CATEGORIA", "").lower()
    emoji = CATEGORY_EMOJI.get(cat, "📌")
    lines = [
        f"{emoji} {item.get('TITULO', '')}",
        item.get("RESUMEN", ""),
        f"📅 {item.get('FECHA', '')}  |  {item.get('FUENTE', '')}",
    ]
    return "\n".join(l for l in lines if l.strip())

def telegram_send(text):
    url  = f"https://api.telegram.org/{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"))

def chunked_send(messages):
    block = ""
    for msg in messages:
        candidate = (block + "\n\n" + msg).strip() if block else msg
        if len(candidate) > 4000:
            if block:
                telegram_send(block)
            block = msg
        else:
            block = candidate
    if block:
        telegram_send(block)

def main():
    if not os.path.exists(REPORT):
        print("Sin informe."); sys.exit(0)
    with open(REPORT, encoding="utf-8") as f:
        content = f.read().strip()
    if "SIN_NOVEDADES" in content:
        print("Sin novedades."); sys.exit(0)
    items = parse_items(content)
    if not items:
        print("Sin ítems válidos."); sys.exit(0)
    seen = load_seen()
    new_items = [i for i in items if item_id(i["TITULO"]) not in seen]
    if not new_items:
        print("Todo ya enviado."); sys.exit(0)
    header = f"🏺 Arte Tribal Africano — {len(new_items)} novedades"
    chunked_send([header] + [format_item(i) for i in new_items])
    for i in new_items:
        seen.add(item_id(i["TITULO"]))
    save_seen(seen)
    print(f"Enviados {len(new_items)} ítems.")

if __name__ == "__main__":
    main()
