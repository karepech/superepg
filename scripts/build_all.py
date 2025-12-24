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

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

PRELIVE = timedelta(minutes=5)

# ================= UTIL =================
def norm(txt: str) -> str:
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t: str) -> datetime:
    base = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) >= 19:
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        base = base.replace(tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm)))
    else:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(WIB)

REPLAY_WORDS = ["replay", "rerun", "highlight", "review", "classic", "full match"]

def is_bad_vol(title, cat):
    t = f"{title} {cat}".lower()
    return any(k in t for k in [
        "badminton", "bwf", "thomas", "uber", "sudirman",
        "volleyball", "volley", "voli", "vnl"
    ])

def is_motogp(title, cat):
    t = f"{title} {cat}".lower()
    return any(k in t for k in ["motogp", "moto gp", "moto2", "moto3", "grand prix", "wsbk"])

def is_liga_indo(title, cat):
    t = f"{title} {cat}".lower()
    return any(k in t for k in ["liga 1", "liga indonesia", "bri liga"])

def valid_live_time(title, cat, start):
    h = start.hour
    t = f"{title} {cat}".lower()

    if is_bad_vol(title, cat):
        return True

    if is_motogp(title, cat):
        return 12 <= h <= 22

    if is_liga_indo(title, cat):
        return 15 <= h <= 21

    if " vs " in f" {t} ":
        return 0 <= h <= 5

    return False

def max_live_end(start, stop, title, cat):
    if is_bad_vol(title, cat):
        return stop if stop else start + timedelta(hours=3)

    if is_motogp(title, cat):
        cap = start + timedelta(hours=4)
        return min(stop, cap) if stop else cap

    cap = start + timedelta(hours=2, minutes=30)
    return min(stop, cap) if stop else cap

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "").strip()
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_channels[cid] = {"key": norm(name), "logo": logo}

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    cat = p.findtext("category", "").strip()
    if not title:
        continue

    if any(w in title.lower() for w in REPLAY_WORDS):
        continue

    start = parse_time(p.get("start"))
    stop = parse_time(p.get("stop")) if p.get("stop") else None

    if not valid_live_time(title, cat, start):
        continue

    live_end = max_live_end(start, stop, title, cat)

    programmes.append({
        "cid": p.get("channel"),
        "title": title,
        "start": start,
        "live_end": live_end
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

m3u_channels = {}
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if not m:
        continue
    m3u_channels.setdefault(norm(m.group(1)), []).append(b)

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

for p in programmes:
    cid = p["cid"]
    if cid not in epg_channels:
        continue

    key = epg_channels[cid]["key"]
    if key not in m3u_channels:
        continue

    live_start = p["start"] - PRELIVE

    for block in m3u_channels[key]:
        if live_start <= NOW <= p["live_end"]:
            label = f'LIVE NOW {p["start"].strftime("%H:%M")} WIB | {p["title"]}'
            out.extend([f'#EXTINF:-1 group-title="LIVE NOW",{label}\n'] + block[1:])
        elif NOW < live_start:
            label = f'NEXT LIVE {p["start"].strftime("%d-%m %H:%M")} WIB | {p["title"]}'
            out.extend([f'#EXTINF:-1 group-title="NEXT LIVE",{label}\n'] + block[1:])

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ FINAL STRICT LIVE: anti replay semua channel (jam-based)")
