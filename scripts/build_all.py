import re
import json
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

LOGO_MAP_FILE = BASE / "mapping" / "logo_channel_map.json"
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# =====================================================
# HELPER
# =====================================================
def parse_time(t: str) -> datetime:
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14:
        try:
            sign = 1 if t[14] == "+" else -1
            hh = int(t[15:17])
            mm = int(t[17:19])
            dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm)))
        except Exception:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

# =====================================================
# LOAD LOGO MAPPING
# =====================================================
with open(LOGO_MAP_FILE, encoding="utf-8") as f:
    logo_map = json.load(f)

# logo_url -> channel_id
LOGO_TO_CHID = {v["logo"]: k for k, v in logo_map.items()}

# =====================================================
# LOAD EPG
# =====================================================
print("📥 Load EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "").strip()
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_channels[cid] = {
            "name": name,
            "logo": logo
        }

for p in root.findall("programme"):
    programmes.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": p.findtext("title", "").strip(),
        "cat": p.findtext("category", "SPORT").strip(),
        "cid": p.get("channel")
    })

# =====================================================
# PARSE M3U (BLOK UTUH)
# =====================================================
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

# =====================================================
# KELOMPOKKAN CHANNEL BERDASARKAN LOGO
# =====================================================
channels_by_logo = {}  # chid -> list of blocks

for block in blocks:
    ext = block[0]
    m_logo = re.search(r'tvg-logo="([^"]+)"', ext)
    if not m_logo:
        continue

    logo = m_logo.group(1)
    if logo not in LOGO_TO_CHID:
        continue

    chid = LOGO_TO_CHID[logo]
    channels_by_logo.setdefault(chid, []).append(block)

# =====================================================
# BUILD LIVE EVENT
# =====================================================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = []

for p in sorted(programmes, key=lambda x: x["start"]):
    if p["cid"] not in epg_channels:
        continue

    epg_logo = epg_channels[p["cid"]]["logo"]

    for blocks_list in channels_by_logo.values():
        for blk in blocks_list:
            if p["start"] <= NOW < p["stop"]:
                title = f'LIVE NOW {p["start"].strftime("%H:%M")} WIB | {p["cat"]} | {p["title"]}'
                live_now.append(
                    [f'#EXTINF:-1 tvg-logo="{epg_logo}" group-title="LIVE NOW",{title}\n']
                    + blk[1:]
                )
            elif p["start"] > NOW:
                title = f'NEXT LIVE {p["start"].strftime("%d-%m %H:%M")} WIB | {p["cat"]} | {p["title"]}'
                next_live.append(
                    [f'#EXTINF:-1 tvg-logo="{epg_logo}" group-title="NEXT LIVE",{title}\n']
                    + blk[1:]
                )

# 🔴 LIVE NOW PALING ATAS
for blk in live_now:
    out.extend(blk)

# ⏭️ NEXT LIVE
for blk in next_live:
    out.extend(blk)

# 📺 CHANNEL NORMAL (SEMUA, NAMA TETAP)
for blk in blocks:
    out.extend(blk)

# =====================================================
# SAVE
# =====================================================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ SUCCESS: LIVE EVENT TERBARU TERINTEGRASI (NAMA TETAP)")
