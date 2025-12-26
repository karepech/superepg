import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUT_NOW = BASE / "live_now.m3u"
OUT_NEXT = BASE / "live_next.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

MAX_CHANNEL = 5
TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

EURO_LEAGUES = [
    "premier league", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions league", "europa league",
    "conference league"
]

BLOCK_WORDS = [
    "md", "highlight", "replay",
    "classic", "review", "recap"
]

CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)

def is_valid_event(title, league):
    t = title.lower()
    l = league.lower()

    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    for w in BLOCK_WORDS:
        if w in t:
            return False

    if not any(x in l for x in EURO_LEAGUES):
        return False

    return True

# ================= LOAD EPG =================
print("📥 Download EPG StarHub")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

live_now_events = []
next_events = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    league = p.findtext("category", "").strip()
    start = p.get("start")

    if not title or not start:
        continue

    if not is_valid_event(title, league):
        continue

    st = parse_time(start)
    day_diff = (st.date() - NOW.date()).days

    if day_diff == 0:
        live_now_events.append(title)
    elif 1 <= day_diff <= 3:
        next_events.append((st, title))

# unik
live_now_events = list(dict.fromkeys(live_now_events))
next_events = list(dict.fromkeys(next_events))

print(f"LIVE NOW: {len(live_now_events)}")
print(f"NEXT LIVE (H+3): {len(next_events)}")

# ================= LOAD BLOK M3U =================
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

# ================= BUILD LIVE NOW =================
out_now = ["#EXTM3U\n"]

for event in live_now_events:
    used = 0
    ek = norm(event)

    for blk in blocks:
        if used >= MAX_CHANNEL:
            break

        if ek[:8] in norm(blk[0]):
            new_blk = blk.copy()
            new_blk[0] = re.sub(
                r",.*$",
                f",LIVE NOW | {event}\n",
                new_blk[0]
            )
            out_now.extend(new_blk)
            used += 1

if len(out_now) == 1 and live_now_events:
    out_now.append(f'#EXTINF:-1 group-title="LIVE NOW",LIVE NOW | {live_now_events[0]}\n')
    out_now.append(CUSTOM_URL + "\n")

# ================= BUILD NEXT LIVE =================
out_next = ["#EXTM3U\n"]

for st, title in sorted(next_events):
    label = st.strftime("%d-%m %H:%M WIB")
    out_next.append(
        f'#EXTINF:-1 group-title="LIVE NEXT",NEXT LIVE | {label} | {title}\n'
    )
    out_next.append(CUSTOM_URL + "\n")

# ================= SAVE =================
OUT_NOW.write_text("".join(out_now), encoding="utf-8")
OUT_NEXT.write_text("".join(out_next), encoding="utf-8")

print("✅ SELESAI: LIVE NOW + NEXT EVENT H+3 (STARHUB)")
