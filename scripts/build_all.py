import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent

EPG_XML = BASE / "epg/epg_wib_sports.xml"
INPUT_M3U = BASE / "m3u/live_epg_sports.m3u"
OUTPUT_M3U = BASE / "output/live_all.m3u"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

OUTPUT_M3U.parent.mkdir(exist_ok=True)

# ================= HELPER =================
def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(TZ)

# ================= LOAD EPG =================
tree = ET.parse(EPG_XML)
root = tree.getroot()

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

# ================= MAP CHANNEL ↔ EPG =================
channel_blocks = {}

for block in blocks:
    extinf = block[0]
    m = re.search(r",(.+)$", extinf)
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
out = [f'#EXTM3U url-tvg="epg/epg_wib_sports.xml"\n']

# 1️⃣ CHANNEL NORMAL
for block in channel_blocks.values():
    out.extend(block)

# 2️⃣ LIVE EVENTS
for start, stop, title, cat, cid in sorted(programmes):
    if cid not in channel_blocks:
        continue

    block = channel_blocks[cid]
    url_line = block[-1]
    logo = epg_by_id[cid]["logo"]

    if start <= NOW < stop:
        name = f"LIVE NOW {start.strftime('%H:%M')} WIB | {cat} | {title}"
        out.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{name}\n'
        )
        out.append(url_line)

    elif start > NOW:
        name = f"NEXT LIVE {start.strftime('%d-%m %H:%M')} WIB | {cat} | {title}"
        out.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",{name}\n'
        )
        out.append(url_line)

# ================= SAVE =================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ SUCCESS: M3U + EPG + LIVE EVENT (AMAN TOKEN & DRM)")
