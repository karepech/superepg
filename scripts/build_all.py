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
CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

BLOCK_WORDS = [
    "md", "highlight", "replay", "classic",
    "recap", "review", "rerun", "magazine"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def has_old_year(title):
    years = re.findall(r"(19\d{2}|20\d{2})", title)
    for y in years:
        if int(y) < 2025:
            return True
    return False

def is_valid_match(title):
    t = title.lower()

    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    if has_old_year(title):
        return False

    for w in BLOCK_WORDS:
        if w in t:
            return False

    return True

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(TZ)

# ================= LOAD EPG =================
print("📥 Load EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

live_now = {}
live_next = {}

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    start_raw = p.get("start")

    if not title or not start_raw:
        continue

    if not is_valid_match(title):
        continue

    try:
        start_time = parse_time(start_raw)
    except:
        continue

    delta = start_time - NOW

    if timedelta(minutes=-120) <= delta <= timedelta(hours=3):
        live_now[title] = start_time
    elif timedelta(hours=3) < delta <= timedelta(days=3):
        live_next[title] = start_time

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

def add_match(title, date_obj, group, use_custom_url):
    used = 0
    key = norm(title)
    date_str = date_obj.strftime("%d-%m-%Y")

    for logo, blks in logo_map.items():
        for blk in blks:
            if used >= MAX_CHANNEL_PER_MATCH:
                return

            if key[:8] in norm(blk[0]):
                new_blk = blk.copy()
                new_blk[0] = re.sub(
                    r",.*$",
                    f',{group} | {date_str} | {title}\n',
                    new_blk[0]
                )

                if use_custom_url:
                    new_blk[-1] = CUSTOM_URL + "\n"

                out.extend(new_blk)
                used += 1

# LIVE NOW
for t, d in live_now.items():
    add_match(t, d, "LIVE NOW", use_custom_url=False)

# LIVE NEXT
for t, d in live_next.items():
    add_match(t, d, "LIVE NEXT", use_custom_url=True)

# fallback aman
if len(out) == 1:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE NOW | Tidak ada pertandingan\n')
    out.append(CUSTOM_URL + "\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("🎉 SELESAI: LIVE FOOTBALL + TANGGAL + FILTER TAHUN")
