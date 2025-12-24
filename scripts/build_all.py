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
NEXT_LIVE_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# ================= HELPER =================
def norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

def is_live_event(title):
    t = title.lower()
    if "replay" in t or "highlight" in t:
        return False
    if "vs" in t:
        return True
    if "live" in t:
        return True
    return False

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

programmes = []
for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not is_live_event(title):
        continue

    programmes.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": title,
        "channel": p.get("channel")
    })

# ================= PARSE M3U =================
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

channels = {}
bein1_block = None

for blk in blocks:
    name = re.search(r",(.+)", blk[0])
    if not name:
        continue
    cname = name.group(1).strip()
    key = norm(cname)
    channels[key] = blk
    if "beinsports1" in key:
        bein1_block = blk

# ================= BUILD =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = {}
live_found = False

for p in programmes:
    if p["start"] <= NOW <= p["stop"]:
        live_found = True
        for blk in channels.values():
            title = f'LIVE NOW | {p["title"]}'
            live_now.append([
                f'#EXTINF:-1 group-title="LIVE NOW",{title}\n'
            ] + blk[1:])

    elif p["start"] > NOW:
        key = p["title"].lower()
        if key not in next_live:
            next_live[key] = [
                f'#EXTINF:-1 group-title="LIVE NEXT",NEXT LIVE {p["start"].strftime("%d-%m %H:%M")} WIB | {p["title"]}\n',
                NEXT_LIVE_URL + "\n"
            ]

# ================= FALLBACK beIN SPORTS 1 =================
if not live_found and bein1_block:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE EVENT\n')
    out.extend(bein1_block[1:])

# ================= OUTPUT =================
for blk in live_now:
    out.extend(blk)

for blk in next_live.values():
    out.extend(blk)

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ BUILD OK | LIVE NOW fallback beIN Sports 1 aktif")
