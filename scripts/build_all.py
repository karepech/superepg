import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================== CONFIG ==================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUT_M3U    = BASE / "live_football.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
TODAY = datetime.now(TZ).date()

MAX_CHANNEL = 5

BLOCK_WORDS = [
    "md", "highlight", "highlights", "classic",
    "replay", "recap", "rerun", "full match"
]

# ================== HELPERS ==================
def norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def is_replay(title):
    t = title.lower()
    return any(w in t for w in BLOCK_WORDS)

def has_old_year(title):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
    for y in years:
        if int(y) < 2025:
            return True
    return False

def is_football(title, category):
    t = title.lower()
    c = category.lower()

    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    football_keys = [
        "league", "liga", "cup", "champions",
        "premier", "bundesliga", "serie",
        "la liga", "uefa", "africa"
    ]
    return any(k in c or k in t for k in football_keys)

# ================== LOAD EPG ==================
print("📥 Download EPG...")
xml_data = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml_data)

events_now = []
events_next = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    cat   = p.findtext("category", "").strip()
    start = p.get("start", "")

    if not title or not start:
        continue

    if is_replay(title):
        continue

    if has_old_year(title):
        continue

    if not is_football(title, cat):
        continue

    dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)
    d  = dt.date()

    if d == TODAY:
        events_now.append((dt, title))
    elif TODAY < d <= TODAY + timedelta(days=3):
        events_next.append((dt, title))

# unik & urut waktu
events_now  = sorted(dict.fromkeys(events_now), key=lambda x: x[0])
events_next = sorted(dict.fromkeys(events_next), key=lambda x: x[0])

print(f"🟢 LIVE NOW  : {len(events_now)}")
print(f"🔵 LIVE NEXT : {len(events_next)}")

# ================== LOAD M3U BLOK ==================
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

# ================== BUILD OUTPUT ==================
out = ["#EXTM3U\n"]

def append_events(events, group):
    for dt, title in events:
        used = 0
        key = norm(title)[:10]

        for blk in blocks:
            if used >= MAX_CHANNEL:
                break

            if key in norm(blk[0]):
                new_blk = blk.copy()
                new_blk[0] = re.sub(
                    r",.*$",
                    f',{group} | {dt.strftime("%d-%m-%Y %H:%M WIB")} | {title}\n',
                    new_blk[0]
                )
                out.extend(new_blk)
                used += 1

append_events(events_now,  "LIVE NOW")
append_events(events_next, "LIVE NEXT")

# fallback kalau kosong
if len(out) == 1:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE NOW | NO LIVE MATCH\n')
    out.append("https://bwifi.my.id/hls/video.m3u8\n")

OUT_M3U.write_text("".join(out), encoding="utf-8")

print("✅ SELESAI: LIVE FOOTBALL (STABIL)")
