import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

PRE_LIVE_MINUTES = 5
MAX_NEXT_DAYS = 3

# ================= HELPERS =================
def norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

def is_match(title):
    t = title.lower()
    return " vs " in t or " v " in t

# ================= LOAD EPG =================
print("📥 Load EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "")
    logo = ""
    if ch.find("icon") is not None:
        logo = ch.find("icon").get("src", "")
    if name:
        epg_channels[cid] = {
            "name": name.strip(),
            "key": norm(name),
            "logo": logo
        }

programmes = []
for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not is_match(title):
        continue

    programmes.append({
        "cid": p.get("channel"),
        "title": title,
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
    })

# ================= PARSE M3U BLOK UTUH =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        blk = [lines[i]]
        i += 1
        while i < len(lines):
            blk.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(blk)
    i += 1

m3u_map = {}
for blk in blocks:
    m = re.search(r",(.+)$", blk[0])
    if m:
        name = m.group(1).strip()
        m3u_map[norm(name)] = blk

# ================= GROUP EVENTS =================
live_now = {}
live_next = {}

for p in programmes:
    cid = p["cid"]
    if cid not in epg_channels:
        continue

    ch = epg_channels[cid]
    key = ch["key"]
    if key not in m3u_map:
        continue

    start = p["start"]
    stop = p["stop"]
    title = p["title"]

    mins_to_start = (start - NOW).total_seconds() / 60
    days_diff = (start.date() - NOW.date()).days

    if start <= NOW <= stop or mins_to_start <= PRE_LIVE_MINUTES and mins_to_start >= -180:
        live_now.setdefault(title, []).append((ch, m3u_map[key], start))
    elif 0 <= days_diff <= MAX_NEXT_DAYS and mins_to_start > PRE_LIVE_MINUTES:
        live_next.setdefault(title, []).append((ch, m3u_map[key], start))

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

# 🔴 LIVE NOW
for title, items in sorted(live_now.items(), key=lambda x: x[1][0][2]):
    for ch, blk, start in items:
        new_blk = blk.copy()
        new_blk[-1] = new_blk[-1]  # URL ASLI

        new_blk[0] = (
            f'#EXTINF:-1 tvg-id="" tvg-logo="{ch["logo"]}" '
            f'group-title="LIVE NOW",'
            f'LIVE NOW | {start.strftime("%H:%M")} WIB | {title}\n'
        )
        out.extend(new_blk)

# ⏭️ LIVE NEXT (SATU PER EVENT)
for title, items in sorted(live_next.items(), key=lambda x: x[1][0][2]):
    ch, blk, start = items[0]

    new_blk = blk.copy()
    new_blk[-1] = CUSTOM_URL + "\n"

    new_blk[0] = (
        f'#EXTINF:-1 tvg-id="" tvg-logo="{ch["logo"]}" '
        f'group-title="LIVE NEXT",'
        f'NEXT LIVE | {start.strftime("%d-%m %H:%M")} WIB | {title}\n'
    )
    out.extend(new_blk)

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ BUILD SELESAI: LIVE NOW & LIVE NEXT")
