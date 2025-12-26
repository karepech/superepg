import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUT_FILE  = BASE / "live_football.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

MAX_CH = 5
H_NEXT = 3

TZ = timezone(timedelta(hours=7))
NOW = datetime.now(TZ)

BLOCK_WORDS = [
    "md", "highlight", "classic", "replay", "rerun",
    "episode", "movie", "drama", "series", "show"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def valid_match(title):
    t = title.lower()
    if "vs" not in t:
        return False
    for b in BLOCK_WORDS:
        if b in t:
            return False
    return True

# ================= LOAD EPG =================
print("📥 Load StarHub EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=60).content)

events = {}

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    start = p.get("start")

    if not title or not start:
        continue
    if not valid_match(title):
        continue

    start_dt = datetime.strptime(
        start[:14], "%Y%m%d%H%M%S"
    ).replace(tzinfo=timezone.utc).astimezone(TZ)

    if start_dt <= NOW + timedelta(days=H_NEXT):
        events[title] = start_dt

print("EVENT TERDETEKSI:", len(events))

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

print("CHANNEL BLOK:", len(blocks))

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]
used_events = set()

for title, dt in events.items():
    key = norm(title)
    used = 0

    for blk in blocks:
        if used >= MAX_CH:
            break

        header = blk[0].lower()
        if "sport" not in header:
            continue

        if key[:8] in norm(header):
            new_blk = blk.copy()

            # GANTI NAMA SAJA
            new_blk[0] = re.sub(
                r",.*$",
                f',LIVE | {dt.strftime("%d-%m %H:%M WIB")} | {title}\n',
                new_blk[0]
            )

            # GANTI URL SAJA
            new_blk[-1] = CUSTOM_URL + "\n"

            out.extend(new_blk)
            used += 1
            used_events.add(title)

# ================= FALLBACK =================
if len(out) == 1:
    out.append('#EXTINF:-1 group-title="LIVE",LIVE FOOTBALL\n')
    out.append(CUSTOM_URL + "\n")

OUT_FILE.write_text("".join(out), encoding="utf-8")

print("✅ SELESAI — BLOK UTUH TERJAGA")
