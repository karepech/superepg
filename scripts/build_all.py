import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# ================= HELPER =================
def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(TZ)

# ================= LOAD EPG =================
print("📥 Download EPG...")
resp = requests.get(EPG_URL, timeout=120)
resp.raise_for_status()
root = ET.fromstring(resp.content)

epg_by_id = {}
epg_by_key = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name")
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""

    if name:
        key = norm(name)
        epg_by_id[cid] = {"name": name.strip(), "logo": logo}
        epg_by_key[key] = cid

for p in root.findall("programme"):
    title = p.findtext("title")
    cat = p.findtext("category", "SPORT")
    start = parse_time(p.get("start"))
    stop = parse_time(p.get("stop"))
    cid = p.get("channel")

    if title and cid in epg_by_id:
        programmes.append((start, stop, title.strip(), cat.strip(), cid))

# ================= PARSE M3U (BLOK UTUH) =================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        block = [lines[i]]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(block)
    i += 1

# ================= MAP CHANNEL =================
channel_blocks = {}

for block in blocks:
    m = re.search(r",(.+)$", block[0])
    if not m:
        continue

    name = m.group(1).strip()
    key = norm(name)

    if key in epg_by_key:
        cid = epg_by_key[key]
        epg = epg_by_id[cid]

        block[0] = (
            f'#EXTINF:-1 '
            f'tvg-id="{cid}" '
            f'tvg-name="{epg["name"]}" '
            f'tvg-logo="{epg["logo"]}" '
            f'group-title="SPORTS",{epg["name"]}\n'
        )

        channel_blocks[cid] = block

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

# 1️⃣ CHANNEL NORMAL
for block in channel_blocks.values():
    out.extend(block)

# 2️⃣ LIVE EVENTS (SALIN BLOK UTUH)
for start, stop, title, cat, cid in sorted(programmes):
    if cid not in channel_blocks:
        continue

    src_block = channel_blocks[cid]
    logo = epg_by_id[cid]["logo"]

    if start <= NOW < stop:
        event_name = f"LIVE NOW {start.strftime('%H:%M')} WIB | {cat} | {title}"
        out.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{event_name}\n'
        )
        out.extend(src_block[1:])  # 🔥 SALIN SEMUA BARIS DRM + URL

    elif start > NOW:
        event_name = f"NEXT LIVE {start.strftime('%d-%m %H:%M')} WIB | {cat} | {title}"
        out.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",{event_name}\n'
        )
        out.extend(src_block[1:])  # 🔥 SALIN SEMUA BARIS DRM + URL

# ================= SAVE =================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ SUCCESS: LIVE EVENT FULL DRM AMAN, TIDAK ERROR")
