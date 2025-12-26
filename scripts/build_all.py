import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================== CONFIG ==================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUT_NOW    = BASE / "live_now.m3u"
OUT_NEXT   = BASE / "live_next.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

MAX_CHANNEL = 5
H_NEXT = 3

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

BLOCK_WORDS = [
    "md","highlight","classic","replay","rerun",
    "episode","ep ","movie","drama","series","show"
]

# ================== HELPERS ==================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_valid_match(title):
    t = title.lower()
    if "vs" not in t:
        return False
    for b in BLOCK_WORDS:
        if b in t:
            return False
    return True

# ================== LOAD EPG ==================
print("📥 Download StarHub EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=60).content)

events_now = {}
events_next = {}

for p in root.findall("programme"):
    title = p.findtext("title","").strip()
    start = p.get("start")

    if not title or not start:
        continue
    if not is_valid_match(title):
        continue

    start_dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)

    if start_dt <= NOW <= start_dt + timedelta(hours=4):
        events_now.setdefault(title, start_dt)
    elif NOW < start_dt <= NOW + timedelta(days=H_NEXT):
        events_next.setdefault(title, start_dt)

print(f"LIVE NOW : {len(events_now)}")
print(f"NEXT LIVE: {len(events_next)}")

# ================== LOAD M3U (BLOK UTUH) ==================
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

# ================== BUILD PLAYLIST ==================
def build(events, outfile, label):
    out = ["#EXTM3U\n"]

    for title, dt in events.items():
        used = 0
        key = norm(title)

        for blk in blocks:
            if used >= MAX_CHANNEL:
                break

            logo = ""
            m = re.search(r'tvg-logo="([^"]+)"', blk[0])
            if m:
                logo = norm(m.group(1))

            if key[:8] in logo:
                new_blk = blk.copy()
                new_blk[0] = re.sub(
                    r",.*$",
                    f',{label} | {dt.strftime("%H:%M WIB")} | {title}\n',
                    new_blk[0]
                )
                new_blk[-1] = CUSTOM_URL + "\n"
                out.extend(new_blk)
                used += 1

    if len(out) == 1:
        out.append(f'#EXTINF:-1 group-title="{label}",{label} | NO EVENT\n')
        out.append(CUSTOM_URL + "\n")

    outfile.write_text("".join(out), encoding="utf-8")

# ================== SAVE ==================
build(events_now, OUT_NOW, "LIVE NOW")
build(events_next, OUT_NEXT, "LIVE NEXT")

print("✅ SELESAI (STABIL & AMAN)")
