import re
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================== KONFIG ==================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_LIVE_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

LIVE_EARLY_MIN = 5      # tampil LIVE NOW 5 menit sebelum kickoff
FOOTBALL_MAX_HOUR = 2  # bola max 2 jam
RACE_MAX_HOUR = 4      # race max 4 jam

CURRENT_YEAR = str(NOW.year)

# ================== HELPER ==================
def norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())

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

def is_replay(title):
    bad = ["replay", "highlight", "ulangan", "recap"]
    return any(b in title.lower() for b in bad)

def is_football(title):
    return "vs" in title.lower()

def has_year(title):
    y = re.findall(r"(20\d{2})", title)
    return any(x != CURRENT_YEAR for x in y)

def has_md(title):
    return "md" in title.lower()

# ================== LOAD EPG ==================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "")
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_channels[cid] = {
            "name": name.strip(),
            "key": norm(name),
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

# ================== PARSE M3U BLOK ==================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

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

m3u_map = {}
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if m:
        m3u_map[norm(m.group(1))] = b

# ================== BUILD LIVE ==================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = []

bein1_block = None
bein1_live_match = False

for p in programmes:
    if p["cid"] not in epg_channels:
        continue

    epg = epg_channels[p["cid"]]
    key = epg["key"]
    if key not in m3u_map:
        continue

    title = p["title"]
    start = p["start"]
    stop = p["stop"]

    # FILTER KERAS
    if is_replay(title):
        continue
    if has_year(title):
        continue

    football = is_football(title)
    md = has_md(title)

    # Football rule
    if football and md and NOW < start:
        continue
    if football and md and NOW > stop:
        continue

    # Timing
    delta_start = (start - NOW).total_seconds() / 60
    delta_end = (NOW - start).total_seconds() / 3600

    is_live = (-LIVE_EARLY_MIN <= delta_start <= 0) or (NOW >= start and NOW <= stop)

    max_hour = FOOTBALL_MAX_HOUR if football else RACE_MAX_HOUR
    if NOW > stop + timedelta(hours=max_hour):
        continue

    block = m3u_map[key]

    is_bein1 = "bein" in epg["name"].lower() and "1" in epg["name"]

    if is_live:
        name = f'LIVE NOW | {title}'
        live_now.append(
            [f'#EXTINF:-1 tvg-logo="{epg["logo"]}" group-title="LIVE NOW",{name}\n']
            + block[1:]
        )
        if is_bein1:
            bein1_live_match = True

    elif start > NOW:
        next_live.append({
            "start": start,
            "title": title,
            "logo": epg["logo"]
        })

        if is_bein1:
            bein1_block = block

# ================== NEXT LIVE (1 EVENT = 1 ITEM) ==================
next_live_sorted = {}
for n in next_live:
    key = f'{n["start"].date()}_{n["title"]}'
    if key not in next_live_sorted:
        next_live_sorted[key] = n

for k in sorted(next_live_sorted, key=lambda x: next_live_sorted[x]["start"]):
    n = next_live_sorted[k]
    out.append(
        f'#EXTINF:-1 tvg-logo="{n["logo"]}" group-title="LIVE NEXT",'
        f'NEXT LIVE {n["start"].strftime("%d-%m %H:%M")} WIB | {n["title"]}\n'
    )
    out.append(f'{NEXT_LIVE_URL}\n')

# ================== LIVE NOW ==================
for b in live_now:
    out.extend(b)

# ================== beIN SPORTS 1 FALLBACK ==================
if not bein1_live_match and bein1_block:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE EVENT\n')
    out.extend(bein1_block[1:])

# ================== SAVE ==================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")

print("✅ BUILD SUCCESS | LIVE NOW & LIVE NEXT ONLY")
