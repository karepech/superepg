import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

MAX_CHANNEL_PER_EVENT = 5
TZ_WIB = timezone(timedelta(hours=7))

EURO_LEAGUES = [
    "premier", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions", "europa", "conference"
]

BLOCK_WORDS = [
    "md", "highlight", "replay", "classic",
    "recap", "review", "hls"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_valid_event(title, league):
    t = title.lower()
    l = league.lower()

    # wajib vs
    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    # buang ulangan
    for w in BLOCK_WORDS:
        if w in t:
            return False

    # liga besar
    if not any(x in l for x in EURO_LEAGUES):
        return False

    return True

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ_WIB)

# ================= LOAD EPG =================
print("📥 Download EPG StarHub")
xml = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml)

now = datetime.now(TZ_WIB)
h3 = now + timedelta(days=3)

live_events = []
next_events = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    league = p.findtext("category", "").strip()

    if not is_valid_event(title, league):
        continue

    start = parse_time(p.attrib["start"])
    stop = parse_time(p.attrib["stop"])

    if start <= now <= stop:
        live_events.append(title)
    elif now < start <= h3:
        next_events.append((start, title))

# unik
live_events = list(dict.fromkeys(live_events))
next_events = sorted(dict.fromkeys(next_events), key=lambda x: x[0])

print(f"🟢 LIVE NOW: {len(live_events)}")
print(f"🟡 NEXT LIVE (H+3): {len(next_events)}")

# ================= LOAD M3U BLOK =================
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

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

def add_event(title, group):
    used = 0
    key = norm(title)[:10]

    for blk in blocks:
        if used >= MAX_CHANNEL_PER_EVENT:
            break

        if key in norm(blk[0]):
            b = blk.copy()
            b[0] = re.sub(
                r",.*$",
                f",{group} | {title}\n",
                b[0]
            )
            out.extend(b)
            used += 1

    # fallback
    if used == 0:
        out.append(f'#EXTINF:-1 group-title="{group}",{group} | {title}\n')
        out.append("https://bwifi.my.id/hls/video.m3u8\n")

# LIVE NOW
for t in live_events:
    add_event(t, "LIVE NOW")

# NEXT LIVE
for st, t in next_events:
    jam = st.strftime("%d-%m %H:%M WIB")
    add_event(f"{jam} | {t}", "LIVE NEXT")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI: LIVE NOW + NEXT H+3 (STARHUB)")
