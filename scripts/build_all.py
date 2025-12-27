import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_football.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

MAX_CHANNEL = 5

BLOCK_WORDS = [
    "md", "replay", "classic", "highlight",
    "ulangan", "recap", "review"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_valid_match(title):
    t = title.lower()

    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    for w in BLOCK_WORDS:
        if w in t:
            return False

    years = re.findall(r"(19\d{2}|20\d{2})", t)
    for y in years:
        if int(y) < 2025:
            return False

    return True

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)

# ================= LOAD EPG =================
print("📥 Download EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

live_now = {}
live_next = {}

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    start = p.get("start")

    if not title or not start:
        continue

    if not is_valid_match(title):
        continue

    start_time = parse_time(start)
    delta_day = (start_time.date() - NOW.date()).days

    if delta_day == 0:
        live_now.setdefault(title, start_time)
    elif 1 <= delta_day <= 3:
        live_next.setdefault(title, start_time)

print(f"LIVE NOW: {len(live_now)}")
print(f"LIVE NEXT H+3: {len(live_next)}")

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

def append_events(events, group):
    for title, st in events.items():
        used = 0
        key = norm(title)[:10]

        for blk in blocks:
            if used >= MAX_CHANNEL:
                break

            if key in norm(blk[0]):
                new_blk = blk.copy()
                new_blk[0] = re.sub(
                    r",.*$",
                    f',LIVE {group} | {st.strftime("%d-%m-%Y %H:%M WIB")} | {title}\n',
                    new_blk[0]
                )
                out.extend(new_blk)
                used += 1

append_events(live_now, "NOW")
append_events(live_next, "NEXT")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI: LIVE FOOTBALL")
