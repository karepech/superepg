import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from collections import defaultdict

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_LIVE_URL = "https://bwifi.my.id/hls/video.m3u8"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

PRELIVE = timedelta(minutes=5)
MAX_DAYS = 3

REPLAY_WORDS = ["replay","rerun","highlight","recap","review","classic"]

# ================= HELPERS =================
def norm(t): return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) >= 19:
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm)))
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)

def bad_replay(title):
    return any(w in title.lower() for w in REPLAY_WORDS)

def valid_event(title):
    t = title.lower()
    if any(k in t for k in ["badminton","bwf","voli","volley","vnl","motogp","moto"]):
        return True
    if " vs " in f" {t} ":
        return True
    return False

def live_end(start, title):
    t = title.lower()
    if "motogp" in t or "moto" in t:
        return start + timedelta(hours=4)
    return start + timedelta(hours=2, minutes=30)

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=60).content)

epg_map = {}
events = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name","")
    if name:
        epg_map[cid] = norm(name)

for p in root.findall("programme"):
    title = p.findtext("title","").strip()
    if not title or bad_replay(title) or not valid_event(title):
        continue

    start = parse_time(p.get("start"))
    if start.date() > (NOW + timedelta(days=MAX_DAYS)).date():
        continue

    events.append({
        "cid": p.get("channel"),
        "title": title,
        "start": start,
        "end": live_end(start, title)
    })

# ================= LOAD M3U =================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        b = [lines[i]]
        i += 1
        while i < len(lines):
            b.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(b)
    i += 1

m3u = defaultdict(list)
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if m:
        m3u[norm(m.group(1))].append(b)

# ================= BUILD =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
next_by_date = defaultdict(list)

for e in events:
    key = epg_map.get(e["cid"])
    if not key or key not in m3u:
        continue

    for blk in m3u[key]:
        logo = re.search(r'tvg-logo="([^"]+)"', blk[0])
        logo = logo.group(1) if logo else ""

        if e["start"] - PRELIVE <= NOW <= e["end"]:
            label = f'LIVE NOW {e["start"].strftime("%H:%M")} WIB | {e["title"]}'
            out.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{label}\n')
            out.extend(blk[1:])

        elif NOW < e["start"]:
            next_by_date[e["start"].date()].append(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",'
                f'{e["start"].strftime("%d %B %Y %H:%M")} WIB | {e["title"]}\n'
            )

# NEXT LIVE URUT TANGGAL
for d in sorted(next_by_date):
    for item in sorted(next_by_date[d]):
        out.append(item)
        out.append(NEXT_LIVE_URL + "\n")

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ FIXED: LIVE NOW akurat, NEXT LIVE H+3, urut tanggal")
