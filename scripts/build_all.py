import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
PLACEHOLDER_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)
TODAY = NOW.date()

LIVE_SWITCH_MIN = 5       # menit sebelum kickoff
FOOTBALL_MAX = 2          # jam
RACE_MAX = 4              # jam

CURRENT_YEAR = str(NOW.year)

# ================= HELPER =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

def is_replay(title):
    bad = [
        "replay", "highlight", "review", "magazine",
        "show", "documentary", "extra time",
        "recap", "talk"
    ]
    return any(x in title.lower() for x in bad)

def has_invalid_year(title):
    years = re.findall(r"\b20\d{2}\b", title)
    for y in years:
        if y != CURRENT_YEAR:
            return True
    return False

def is_match(title):
    t = title.lower()
    if any(x in t for x in ["badminton", "volley", "voli", "motogp", "race"]):
        return True
    return "vs" in t

# ================= LOAD EPG =================
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
            "key": norm(name),
            "logo": logo
        }

for p in root.findall("programme"):
    programmes.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": p.findtext("title", "").strip(),
        "cid": p.get("channel")
    })

# ================= PARSE M3U (BLOK UTUH) =================
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
bein1_block = None

for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if not m:
        continue
    name = m.group(1).strip()
    key = norm(name)
    m3u_map[key] = b
    if "beinsports1" in key:
        bein1_block = b

# ================= BUILD =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now_blocks = []
next_live_map = {}
bein1_live_detected = False

for p in programmes:
    if p["cid"] not in epg_channels:
        continue

    ch = epg_channels[p["cid"]]
    key = ch["key"]
    if key not in m3u_map:
        continue

    title = p["title"]
    start = p["start"]
    stop = p["stop"]
    event_day = start.date()

    # FILTER DASAR
    if is_replay(title):
        continue
    if has_invalid_year(title):
        continue
    if not is_match(title):
        continue

    minutes_to_start = (start - NOW).total_seconds() / 60
    hours_from_start = (NOW - start).total_seconds() / 3600

    max_hour = FOOTBALL_MAX if "vs" in title.lower() else RACE_MAX
    if hours_from_start > max_hour:
        continue

    # ================= H0 → LIVE NOW =================
    if event_day == TODAY:
        # Tentukan URL
        if minutes_to_start <= LIVE_SWITCH_MIN:
            body = m3u_map[key][1:]
            if "beinsports1" in key:
                bein1_live_detected = True
        else:
            body = [PLACEHOLDER_URL + "\n"]

        live_now_blocks.append(
            [f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="LIVE NOW",'
             f'LIVE NOW {start.strftime("%H:%M")} WIB | {title}\n']
            + body
        )

    # ================= NEXT LIVE (H+1 s/d H+3) =================
    elif TODAY < event_day <= TODAY + timedelta(days=3):
        k = norm(title)
        if k not in next_live_map:
            next_live_map[k] = {
                "title": title,
                "time": start,
                "logo": ch["logo"]
            }

# ================= OUTPUT URUTAN FINAL =================

# 1️⃣ LIVE EVENT (PALING ATAS)
if not bein1_live_detected and bein1_block:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE EVENT\n')
    out.extend(bein1_block[1:])

# 2️⃣ LIVE NOW (PERTANDINGAN + JAM)
for b in live_now_blocks:
    out.extend(b)

# 3️⃣ LIVE NEXT
for k in sorted(next_live_map, key=lambda x: next_live_map[x]["time"]):
    ev = next_live_map[k]
    out.append(
        f'#EXTINF:-1 tvg-logo="{ev["logo"]}" group-title="LIVE NEXT",'
        f'NEXT LIVE {ev["time"].strftime("%d-%m %H:%M")} WIB | {ev["title"]}\n'
    )
    out.append(f'{PLACEHOLDER_URL}\n')

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ FINAL BUILD OK | LIVE EVENT first, LIVE NOW with time")
