import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# =====================================================
# KONFIG
# =====================================================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# =====================================================
# HELPER PARSE TIME (WIB FIX)
# =====================================================
def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14:
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        dt = dt.replace(
            tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm))
        )
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

# =====================================================
# PARSE M3U → SIMPAN BLOK CHANNEL UTUH
# =====================================================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

channels = []
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
        channels.append(block)
    i += 1

# =====================================================
# LOAD & PARSE EPG
# =====================================================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

live_now = []
next_live = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not title:
        continue

    start = parse_time(p.get("start"))
    stop = parse_time(p.get("stop"))
    cat = p.findtext("category", "SPORT").strip()

    if start <= NOW < stop:
        live_now.append((start, title, cat))
    elif start > NOW:
        next_live.append((start, title, cat))

# =====================================================
# BUILD PLAYLIST (LIVE ONLY)
# =====================================================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

# 🔴 LIVE NOW (PALING ATAS)
for start, title, cat in sorted(live_now, key=lambda x: x[0]):
    label = f'LIVE NOW {start.strftime("%H:%M")} WIB | {cat} | {title}'
    for ch in channels:
        out.append(f'#EXTINF:-1 group-title="LIVE NOW",{label}\n')
        out.extend(ch[1:])

# ⏭ NEXT LIVE
for start, title, cat in sorted(next_live, key=lambda x: x[0]):
    label = f'NEXT LIVE {start.strftime("%d-%m %H:%M")} WIB | {cat} | {title}'
    for ch in channels:
        out.append(f'#EXTINF:-1 group-title="NEXT LIVE",{label}\n')
        out.extend(ch[1:])

# =====================================================
# SAVE
# =====================================================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ LIVE NOW & NEXT LIVE ONLY — SEMUA CHANNEL TAMPIL, TANPA ERROR")
