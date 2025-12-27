import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_football.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

MAX_CHANNEL_PER_MATCH = 5

# kata yang PASTI ulangan
BLOCK_WORDS = [
    "md", "highlight", "replay", "classic",
    "recap", "review", "rerun", "magazine"
]

# ================= HELPER =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_replay(title):
    t = title.lower()
    return any(w in t for w in BLOCK_WORDS)

def is_match(title):
    return bool(re.search(r"\bvs\b|\bv\b", title.lower()))

# ================= LOAD EPG =================
print("📥 Download EPG")
xml = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml)

live_now = []
live_next = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    start = p.get("start", "")[:14]

    if not title or not start:
        continue

    if not is_match(title):
        continue

    if is_replay(title):
        continue

    try:
        start_time = datetime.strptime(start, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)
    except:
        continue

    delta = start_time - NOW

    if timedelta(minutes=-120) <= delta <= timedelta(hours=3):
        live_now.append(title)
    elif timedelta(hours=3) < delta <= timedelta(days=3):
        live_next.append(title)

# unik
live_now = list(dict.fromkeys(live_now))
live_next = list(dict.fromkeys(live_next))

print(f"✅ LIVE NOW : {len(live_now)}")
print(f"✅ LIVE NEXT (H+3): {len(live_next)}")

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

# ================= INDEX BLOK BY LOGO =================
logo_map = {}

for blk in blocks:
    m = re.search(r'tvg-logo="([^"]+)"', blk[0])
    if m:
        logo = m.group(1)
        logo_map.setdefault(logo, []).append(blk)

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

def add_match(title, group, use_custom_url):
    used = 0
    title_key = norm(title)

    for logo, blks in logo_map.items():
        for blk in blks:
            if used >= MAX_CHANNEL_PER_MATCH:
                return

            if title_key[:8] in norm(blk[0]):
                new_blk = blk.copy()
                new_blk[0] = re.sub(
                    r",.*$",
                    f',{group} | {title}\n',
                    new_blk[0]
                )

                if use_custom_url:
                    new_blk[-1] = "https://bwifi.my.id/hls/video.m3u8\n"

                out.extend(new_blk)
                used += 1

# LIVE NOW
for t in live_now:
    add_match(t, "LIVE NOW", use_custom_url=False)

# LIVE NEXT
for t in live_next:
    add_match(t, "LIVE NEXT", use_custom_url=True)

# fallback aman
if len(out) == 1:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE NOW | Tidak ada pertandingan\n')
    out.append("https://bwifi.my.id/hls/video.m3u8\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("🎉 SELESAI: LIVE FOOTBALL (STABIL)")
