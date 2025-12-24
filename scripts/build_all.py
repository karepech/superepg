import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from collections import defaultdict

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_LIVE_URL = "https://bwifi.my.id/hls/video.m3u8"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

PRELIVE = timedelta(minutes=5)
MAX_DAYS = 3

# ================= REPLAY FILTER =================
BAD_WORDS = [
    "replay", "rerun", "highlight", "highlights",
    "recap", "review", "classic",
    " hl", " hls"
]

# ================= UTIL =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

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

def extract_logo(extinf):
    m = re.search(r'tvg-logo="([^"]+)"', extinf)
    return m.group(1) if m else ""

def extract_stream(block):
    for l in block:
        if l.startswith("http"):
            return l.strip()
    return ""

def is_stream_alive(url):
    if not url:
        return False
    if url.endswith(".mpd") or "clearkey" in url.lower():
        return True
    try:
        r = requests.head(url, timeout=4, allow_redirects=True)
        return r.status_code < 400
    except:
        return False

# ================= EVENT FILTER =================
def is_bad_event(title):
    t = " " + title.lower() + " "
    if any(w in t for w in BAD_WORDS):
        return True
    # MD boleh jika ada LIVE
    if " md" in t and "live" not in t:
        return True
    return False

def is_valid_event(title, cat):
    t = f"{title} {cat}".lower()
    if any(k in t for k in ["badminton","bwf","voli","volley","vnl"]):
        return True
    if any(k in t for k in ["motogp","moto2","moto3","grand prix"]):
        return True
    if any(k in t for k in ["afc champions","afc cup","liga 1","liga indonesia","bri liga"]):
        return True
    if " vs " in f" {t} ":
        return True
    return False

def live_end_time(start, stop, title):
    t = title.lower()
    if any(k in t for k in ["badminton","bwf","voli","volley","vnl"]):
        return stop if stop else start + timedelta(hours=3)
    if "moto" in t:
        cap = start + timedelta(hours=4)
        return min(stop, cap) if stop else cap
    cap = start + timedelta(hours=2, minutes=30)
    return min(stop, cap) if stop else cap

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=60).content)

epg_channel_map = {}
for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name","")
    if name:
        epg_channel_map[cid] = norm(name)

events = []
for p in root.findall("programme"):
    title = p.findtext("title","").strip()
    cat = p.findtext("category","").strip()
    if not title or is_bad_event(title) or not is_valid_event(title, cat):
        continue

    start = parse_time(p.get("start"))
    if start.date() > (NOW + timedelta(days=MAX_DAYS)).date():
        continue

    stop = parse_time(p.get("stop")) if p.get("stop") else None

    events.append({
        "cid": p.get("channel"),
        "title": title,
        "start": start,
        "end": live_end_time(start, stop, title)
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

m3u_map = defaultdict(list)
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if m:
        m3u_map[norm(m.group(1))].append(b)

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
next_seen = set()
next_events = defaultdict(list)

for e in events:
    key = epg_channel_map.get(e["cid"])
    if not key or key not in m3u_map:
        continue

    live_start = e["start"] - PRELIVE

    for blk in m3u_map[key]:
        logo = extract_logo(blk[0])
        stream = extract_stream(blk)

        if live_start <= NOW <= e["end"]:
            if not is_stream_alive(stream):
                continue
            label = f'LIVE NOW {e["start"].strftime("%H:%M")} WIB | {e["title"]}'
            out.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{label}\n')
            out.extend(blk[1:])

        elif NOW < e["start"]:
            uid = f'{e["title"]}_{e["start"].date()}'
            if uid in next_seen:
                continue
            next_seen.add(uid)
            next_events[e["start"].date()].append(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",'
                f'{e["start"].strftime("%d %B %Y %H:%M")} WIB | {e["title"]}\n'
            )

# NEXT LIVE URUT PER TANGGAL
for d in sorted(next_events):
    for item in sorted(next_events[d]):
        out.append(item)
        out.append(NEXT_LIVE_URL + "\n")

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ FINAL OK: LIVE multi-channel, NEXT single per match, lokal sync")
