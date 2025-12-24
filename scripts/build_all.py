import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import requests

# =====================================================
# KONFIG
# =====================================================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"
LOGO_MAP_FILE = BASE / "mapping" / "logo_channel_map.json"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# =====================================================
# HELPER
# =====================================================
def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14:
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm)))
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

# =====================================================
# LOAD LOGO MAPPING
# =====================================================
with open(LOGO_MAP_FILE, encoding="utf-8") as f:
    logo_map = json.load(f)

LOGO_TO_CHID = {v["logo"]: k for k, v in logo_map.items()}

# =====================================================
# PARSE M3U → SIMPAN BLOK PER LOGO (URL UTUH)
# =====================================================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

logo_blocks = defaultdict(list)

i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        ext = lines[i]
        block = [ext]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1

        m = re.search(r'tvg-logo="([^"]+)"', ext)
        if m:
            logo_blocks[m.group(1)].append(block)
    i += 1

# =====================================================
# LOAD EPG
# =====================================================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

programmes = []
for p in root.findall("programme"):
    programmes.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": p.findtext("title", "").strip(),
        "cat": p.findtext("category", "SPORT").strip(),
        "cid": p.get("channel")
    })

# =====================================================
# BUILD LIVE ONLY
# =====================================================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
used_events = set()

def add_event(p, label):
    for logo, blocks in logo_blocks.items():
        if logo in LOGO_TO_CHID and blocks:
            blk = blocks[0]  # ambil SATU URL saja
            key = (label, p["title"], p["start"])
            if key in used_events:
                return
            used_events.add(key)

            title = (
                f'{label} {p["start"].strftime("%H:%M")} WIB | '
                f'{p["cat"]} | {p["title"]}'
            )
            out.append(
                f'#EXTINF:-1 group-title="{label}",{title}\n'
            )
            out.extend(blk[1:])
            return

for p in sorted(programmes, key=lambda x: x["start"]):
    if p["start"] <= NOW < p["stop"]:
        add_event(p, "LIVE NOW")
    elif p["start"] > NOW:
        add_event(p, "NEXT LIVE")

# =====================================================
# SAVE
# =====================================================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ LIVE NOW & NEXT LIVE ONLY — FILE RINGAN & AMAN")
